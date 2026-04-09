"""
test_api.py — Integration tests for the Green Landscape AI Lead Engine API.

Requires a running server:
    uvicorn src.api.main:app --reload --port 8000

Usage:
    python tools/scripts/test_api.py
    python tools/scripts/test_api.py --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import sys

import httpx

BASE_URL = "http://localhost:8000"

PASS = "[PASS]"
FAIL = "[FAIL]"

results: list[tuple[str, bool, str]] = []


def run(label: str, fn):
    """Run a single test function, catch all exceptions, record result."""
    try:
        fn()
        results.append((label, True, ""))
        print(f"  {PASS} {label}")
    except AssertionError as exc:
        results.append((label, False, str(exc)))
        print(f"  {FAIL} {label} — {exc}")
    except Exception as exc:
        results.append((label, False, f"{type(exc).__name__}: {exc}"))
        print(f"  {FAIL} {label} — {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def assert_status(resp: httpx.Response, expected: int):
    if resp.status_code != expected:
        raise AssertionError(
            f"Expected HTTP {expected}, got {resp.status_code}. Body: {resp.text[:200]}"
        )


def assert_key(data: dict, key: str):
    if key not in data:
        raise AssertionError(f"Key '{key}' missing from response: {list(data.keys())}")


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_health():
    resp = httpx.get(f"{BASE_URL}/health", timeout=10)
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "status")
    assert_key(data, "service")
    if data["status"] != "ok":
        raise AssertionError(f"Expected status='ok', got '{data['status']}'")
    if "green-landscape" not in data["service"]:
        raise AssertionError(f"Unexpected service name: '{data['service']}'")


def test_score_high():
    """Score a high-quality lead — should return action='call'."""
    payload = {
        "source": "permits",
        "source_id": "TEST-001",
        "signal": "new irrigation system permit approved",
        "signal_type": "new_construction",
        "zip_code": "33602",
        "phone": "8135550001",
        "email": "test@example.com",
        "property_type": "residential",
    }
    resp = httpx.post(f"{BASE_URL}/score", json=payload, timeout=10)
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "score")
    assert_key(data, "reason")
    assert_key(data, "action")
    if data["action"] not in ("call", "review", "discard"):
        raise AssertionError(f"Invalid action value: '{data['action']}'")
    if data["score"] < 55:
        raise AssertionError(
            f"Expected score >= 55 for high-quality lead, got {data['score']}. "
            f"Reason: {data['reason']}"
        )
    if data["action"] != "call":
        raise AssertionError(
            f"Expected action='call' for score {data['score']}, got '{data['action']}'"
        )


def test_score_low():
    """Score a low-quality lead — should return action='discard'."""
    payload = {
        "source": "reddit",
        "signal_type": "unknown",
        # No phone, no zip, no useful signals
    }
    resp = httpx.post(f"{BASE_URL}/score", json=payload, timeout=10)
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "score")
    assert_key(data, "action")
    if data["action"] != "discard":
        raise AssertionError(
            f"Expected action='discard' for low-quality lead, got '{data['action']}' "
            f"(score={data['score']})"
        )


def test_leads_list():
    """GET /leads?status=new should return a paginated list."""
    resp = httpx.get(f"{BASE_URL}/leads", params={"status": "new"}, timeout=10)
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "leads")
    assert_key(data, "count")
    if not isinstance(data["leads"], list):
        raise AssertionError(f"Expected 'leads' to be a list, got {type(data['leads'])}")
    if data["count"] != len(data["leads"]):
        raise AssertionError(
            f"count={data['count']} does not match len(leads)={len(data['leads'])}"
        )


def test_leads_list_queued():
    """GET /leads?status=queued should also work."""
    resp = httpx.get(
        f"{BASE_URL}/leads",
        params={"status": "queued", "limit": 10},
        timeout=10,
    )
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "leads")


def test_ingest_valid():
    """POST /ingest with 1 valid lead should return a summary dict."""
    payload = {
        "leads": [
            {
                "source": "test_script",
                "source_id": "TEST-INGEST-001",
                "name": "Jane Homeowner",
                "phone": "8135550099",
                "email": "jane@example.com",
                "address": "123 Oak Ave",
                "city": "Tampa",
                "zip_code": "33609",
                "signal": "Needs sprinkler repair urgently",
                "signal_type": "request",
                "property_type": "residential",
            }
        ]
    }
    resp = httpx.post(f"{BASE_URL}/ingest", json=payload, timeout=30)
    assert_status(resp, 200)
    data = resp.json()
    for key in ("total", "inserted", "duplicates", "discarded", "queued_for_call",
                "queued_for_review", "errors"):
        assert_key(data, key)
    if data["total"] != 1:
        raise AssertionError(f"Expected total=1, got {data['total']}")
    if data["errors"] != 0:
        raise AssertionError(
            f"Expected 0 errors, got {data['errors']}. "
            "Check server logs for the exception."
        )


def test_ingest_empty():
    """POST /ingest with empty list should return HTTP 400."""
    resp = httpx.post(f"{BASE_URL}/ingest", json={"leads": []}, timeout=10)
    assert_status(resp, 400)


def test_vapi_webhook_ignored():
    """POST /vapi/outcome with a non-end-of-call event should be ignored gracefully."""
    payload = {"type": "call-started", "call": {"id": "test-call-id"}}
    resp = httpx.post(f"{BASE_URL}/vapi/outcome", json=payload, timeout=10)
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "status")
    if data["status"] != "ignored":
        raise AssertionError(f"Expected status='ignored', got '{data['status']}'")


def test_vapi_webhook_end_of_call():
    """POST /vapi/outcome with end-of-call-report should be accepted."""
    payload = {
        "type": "end-of-call-report",
        "call": {
            "id": "test-vapi-call-999",
            "customer": {"number": "+18135550000", "name": "Test Lead"},
            "durationSeconds": 45,
            "successEvaluation": "false",
            "transcript": "Agent: Hi! Customer: No thanks.",
            "summary": "Customer was not interested.",
        },
    }
    resp = httpx.post(f"{BASE_URL}/vapi/outcome", json=payload, timeout=10)
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "status")
    if data["status"] != "accepted":
        raise AssertionError(f"Expected status='accepted', got '{data['status']}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global BASE_URL

    parser = argparse.ArgumentParser(description="Test the Green Landscape Lead Engine API")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Server base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    BASE_URL = args.base_url.rstrip("/")

    print(f"\nGreen Landscape AI Lead Engine — API Tests")
    print(f"Target: {BASE_URL}\n")

    # Check server reachability first
    try:
        httpx.get(f"{BASE_URL}/health", timeout=5)
    except Exception as exc:
        print(f"ERROR: Cannot reach server at {BASE_URL}")
        print(f"       {type(exc).__name__}: {exc}")
        print(f"\nStart the server first:")
        print(f"  uvicorn src.api.main:app --reload --port 8000\n")
        sys.exit(1)

    # Run all tests
    print("Running tests...\n")
    run("GET  /health — liveness check", test_health)
    run("POST /score — high-quality lead (expect action=call)", test_score_high)
    run("POST /score — low-quality lead (expect action=discard)", test_score_low)
    run("GET  /leads?status=new — list leads", test_leads_list)
    run("GET  /leads?status=queued&limit=10 — filtered list", test_leads_list_queued)
    run("POST /ingest — 1 valid lead", test_ingest_valid)
    run("POST /ingest — empty list (expect 400)", test_ingest_empty)
    run("POST /vapi/outcome — non-end-of-call event (expect ignored)", test_vapi_webhook_ignored)
    run("POST /vapi/outcome — end-of-call-report (expect accepted)", test_vapi_webhook_end_of_call)

    # Summary
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    print(f"\n{'=' * 50}")
    if failed == 0:
        print(f"All {total} tests passed.")
    else:
        print(f"{failed} of {total} tests FAILED:")
        for label, ok, msg in results:
            if not ok:
                print(f"  - {label}")
                print(f"    {msg}")
    print(f"{'=' * 50}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
