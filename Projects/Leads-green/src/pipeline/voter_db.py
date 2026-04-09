"""
Florida Voter File — phone enrichment via local SQLite lookup.

The Florida voter registration file is a public record under FL Statute 97.0585.
It includes name, address, phone, and party for all registered voters.

HOW TO GET THE FILE (free, one-time):
  1. Go to: https://dos.myflorida.com/elections/data-statistics/
             voter-registration-statistics/voter-registration-file/
  2. Fill out the "Voter Registration Data Request" form
  3. Select: County = Hillsborough, File Format = Tab-delimited
  4. Submit — you'll receive a .txt or .zip file by email (usually same day)

  Alternatively, request directly from Hillsborough County SOE:
  https://www.hillsboroughsoe.gov/  |  Phone: (813) 744-5900

FILE FORMAT (tab-delimited, no header):
  Fields (positions vary by year — see FIELD_MAP below for current layout):
  County, VoterID, LastName, FirstName, MiddleName, Suffix, Addr1, Addr2,
  City, State, ZIP, DOB, Race, Sex, Party, PrecNum, Phone, Email, ...

USAGE:
  # Load the voter file into SQLite (one-time, ~2 minutes for Hillsborough):
  python -m src.pipeline.voter_db load --file /path/to/HillsboroughVoters.txt

  # Test a lookup:
  python -m src.pipeline.voter_db lookup --name "John Smith" --zip "33602"

  # Run enrichment against all review leads:
  python -m src.pipeline.voter_db enrich
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

from loguru import logger

from src.persistence.client import get_supabase, update_lead
from src.pipeline.scorer import score_lead

# SQLite DB stored alongside the project data
DB_PATH = Path(__file__).parents[2] / "data" / "voter_phones.db"

# Florida voter file field positions (0-indexed, tab-delimited)
# Layout as of 2024 extract — adjust if columns shift
FIELD_MAP = {
    "county":     0,
    "voter_id":   1,
    "last_name":  3,
    "first_name": 4,
    "middle":     5,
    "suffix":     6,
    "addr1":      7,
    "city":       9,
    "zip":        11,
    "phone":      19,
}

CALL_THRESHOLD = 55

_PHONE_RE = re.compile(r"\+?1?[-.\s]?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})")


def _normalize_phone(raw: str) -> str | None:
    m = _PHONE_RE.search(raw.strip())
    if m:
        return f"+1{''.join(m.groups())}"
    return None


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse spaces."""
    name = re.sub(r"[^\w\s]", "", name.lower())
    return " ".join(name.split())


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voters (
            voter_id   TEXT PRIMARY KEY,
            first_name TEXT,
            last_name  TEXT,
            full_name  TEXT,
            zip        TEXT,
            phone      TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_zip ON voters(zip)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_last ON voters(last_name)")
    conn.commit()


def load_voter_file(file_path: str, batch_size: int = 10_000) -> dict:
    """
    Parse the Florida voter tab-delimited file and load into SQLite.
    Skips rows with no phone number.

    Args:
        file_path: Path to the voter file (.txt, tab-delimited)
        batch_size: Insert batch size for performance

    Returns:
        Summary dict with rows_read, rows_loaded, rows_skipped.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    rows_read = 0
    rows_loaded = 0
    rows_skipped = 0
    batch = []

    with open(file_path, encoding="latin-1", errors="replace") as f:
        for line in f:
            rows_read += 1
            fields = line.rstrip("\n").split("\t")

            if len(fields) <= max(FIELD_MAP.values()):
                rows_skipped += 1
                continue

            raw_phone = fields[FIELD_MAP["phone"]].strip()
            phone = _normalize_phone(raw_phone)
            if not phone:
                rows_skipped += 1
                continue

            first = fields[FIELD_MAP["first_name"]].strip()
            last = fields[FIELD_MAP["last_name"]].strip()
            voter_id = fields[FIELD_MAP["voter_id"]].strip()
            zip_code = fields[FIELD_MAP["zip"]].strip()[:5]
            full = _normalize_name(f"{first} {last}")

            batch.append((voter_id, first.lower(), last.lower(), full, zip_code, phone))

            if len(batch) >= batch_size:
                conn.executemany(
                    "INSERT OR REPLACE INTO voters VALUES (?,?,?,?,?,?)", batch
                )
                conn.commit()
                rows_loaded += len(batch)
                batch.clear()
                logger.debug(f"[voter_db] Loaded {rows_loaded:,} rows...")

    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO voters VALUES (?,?,?,?,?,?)", batch
        )
        conn.commit()
        rows_loaded += len(batch)

    conn.close()
    summary = {"rows_read": rows_read, "rows_loaded": rows_loaded, "rows_skipped": rows_skipped}
    logger.info(f"[voter_db] Load complete: {summary}")
    return summary


def lookup_phone(name: str, zip_code: str) -> str | None:
    """
    Look up a phone number by owner name + ZIP code.

    Tries exact last name match first, then fuzzy first-word match.
    Returns the first phone found, or None.
    """
    if not DB_PATH.exists():
        logger.debug("[voter_db] voter_phones.db not found — run 'voter_db load' first")
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Parse name: handle "LAST FIRST", "FIRST LAST", "First And Second Last", LLC names
    parts = _normalize_name(name).split()
    if not parts:
        conn.close()
        return None

    # Try each word as a last name (deed records often list "SMITH JOHN" or "JOHN SMITH")
    zip5 = str(zip_code).strip()[:5]

    for last_candidate in parts:
        if len(last_candidate) < 2:
            continue
        rows = conn.execute(
            "SELECT phone FROM voters WHERE last_name=? AND zip=? LIMIT 5",
            (last_candidate, zip5),
        ).fetchall()

        if rows:
            # Multiple matches — try to narrow by first name
            remaining = [p for p in parts if p != last_candidate]
            for row in rows:
                conn.close()
                return row["phone"]

    conn.close()
    return None


def run_voter_enrichment(limit: int = 500, delay: float = 0.05) -> dict:
    """
    Enrich review leads using the local voter file DB.
    Much faster than SerpAPI — no rate limits, no API cost.
    """
    if not DB_PATH.exists():
        logger.error(
            "[voter_db] voter_phones.db not found. "
            "Run: python -m src.pipeline.voter_db load --file <path>"
        )
        return {"error": "DB not found"}

    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("*")
        .eq("status", "new")
        .is_("phone", "null")
        .gte("score", 20)
        .not_.is_("name", "null")
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )

    leads = result.data
    logger.info(f"[voter_db] Enriching {len(leads)} review leads from voter file")

    enriched = 0
    upgraded = 0
    skipped = 0

    for lead in leads:
        name = (lead.get("name") or "").strip()
        zip_code = (lead.get("zip_code") or "").strip()

        phone = lookup_phone(name, zip_code)

        if not phone:
            skipped += 1
            time.sleep(delay)
            continue

        enriched += 1
        lead_with_phone = {**lead, "phone": phone}
        new_scoring = score_lead(lead_with_phone)

        update_fields = {
            "phone": phone,
            "score": new_scoring.score,
            "score_reason": new_scoring.reason,
        }

        if new_scoring.action == "call":
            update_fields["status"] = "queued"
            upgraded += 1
            logger.success(
                f"[voter_db] Lead {lead['id'][:8]} -> CALL score={new_scoring.score} phone={phone}"
            )
        else:
            logger.info(
                f"[voter_db] Lead {lead['id'][:8]} phone found, score={new_scoring.score} -> REVIEW"
            )

        update_lead(lead["id"], update_fields)
        time.sleep(delay)

    summary = {"processed": len(leads), "enriched": enriched, "upgraded_to_call": upgraded, "skipped": skipped}
    logger.info(f"[voter_db] Done: {summary}")
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Voter file phone enrichment")
    sub = parser.add_subparsers(dest="cmd")

    p_load = sub.add_parser("load", help="Load voter file into SQLite")
    p_load.add_argument("--file", required=True, help="Path to voter .txt file")

    p_lookup = sub.add_parser("lookup", help="Test a single name+zip lookup")
    p_lookup.add_argument("--name", required=True)
    p_lookup.add_argument("--zip", required=True)

    p_enrich = sub.add_parser("enrich", help="Enrich all review leads from voter DB")
    p_enrich.add_argument("--limit", type=int, default=500)

    args = parser.parse_args()

    if args.cmd == "load":
        result = load_voter_file(args.file)
        print(f"\nVoter file loaded:")
        print(f"  Read:    {result['rows_read']:,}")
        print(f"  Loaded:  {result['rows_loaded']:,}")
        print(f"  Skipped: {result['rows_skipped']:,}")
        print(f"\nDB saved to: {DB_PATH}")

    elif args.cmd == "lookup":
        phone = lookup_phone(args.name, args.zip)
        print(f"Phone for '{args.name}' in {args.zip}: {phone or 'NOT FOUND'}")

    elif args.cmd == "enrich":
        result = run_voter_enrichment(limit=args.limit)
        print(f"\nVoter enrichment complete:")
        print(f"  Processed:        {result.get('processed', 0)}")
        print(f"  Found phone:      {result.get('enriched', 0)}")
        print(f"  Upgraded to call: {result.get('upgraded_to_call', 0)}")
        print(f"  No match:         {result.get('skipped', 0)}")

    else:
        parser.print_help()
