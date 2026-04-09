"""
POST /ingest — bulk ingest raw leads from scrapers or n8n
GET  /leads  — list leads by status for dashboard
GET  /leads/stats — summary counts by status and period
GET  /leads/route — ordered field-visit route for no-phone leads
"""
from __future__ import annotations
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.persistence.client import get_leads_by_status, get_supabase
from src.persistence.models import LeadRaw
from src.pipeline.enricher import geocode_address as _census_geocode


def geocode_address(address: str):
    """Try Census geocoder first, fall back to Nominatim (OpenStreetMap)."""
    result = _census_geocode(address)
    if result:
        return result
    try:
        import httpx
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "GreenLandscapeLeadEngine/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None
from src.pipeline.runner import PipelineResult, run_pipeline


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _nearest_neighbor_route(start_lat: float, start_lon: float, leads: list[dict]) -> list[dict]:
    """Nearest-neighbor TSP approximation starting from (start_lat, start_lon)."""
    unvisited = [l for l in leads if l.get("lat") and l.get("lon")]
    route = []
    cur_lat, cur_lon = start_lat, start_lon
    while unvisited:
        nearest = min(unvisited, key=lambda l: _haversine_miles(cur_lat, cur_lon, l["lat"], l["lon"]))
        dist = _haversine_miles(cur_lat, cur_lon, nearest["lat"], nearest["lon"])
        nearest = {**nearest, "distance_miles": round(dist, 2)}
        route.append(nearest)
        cur_lat, cur_lon = nearest["lat"], nearest["lon"]
        unvisited.remove(next(l for l in unvisited if l["id"] == nearest["id"]))
    return route

router = APIRouter(tags=["leads"])


class IngestRequest(BaseModel):
    leads: list[LeadRaw]


class IngestResponse(BaseModel):
    total: int
    inserted: int
    duplicates: int
    discarded: int
    queued_for_call: int
    queued_for_review: int
    errors: int


@router.post("/ingest", response_model=IngestResponse)
async def ingest_leads(req: IngestRequest):
    if not req.leads:
        raise HTTPException(status_code=400, detail="No leads provided")

    result: PipelineResult = run_pipeline(req.leads)
    return IngestResponse(
        total=result.total,
        inserted=result.inserted,
        duplicates=result.duplicates,
        discarded=result.discarded,
        queued_for_call=result.queued_for_call,
        queued_for_review=result.queued_for_review,
        errors=result.errors,
    )


@router.get("/leads/route")
async def field_route(
    start: str = Query("11510 Spring Hill Dr, Spring Hill FL 34609", description="Starting address"),
    limit: int = Query(80, ge=1, le=300),
):
    """
    Returns an optimized door-to-door route of no-phone leads,
    starting from `start` and visiting nearest leads first.
    """
    # Geocode the start address
    coords = geocode_address(start)
    if not coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode start address: {start}")
    start_lat, start_lon = coords

    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("id,name,address,city,zip_code,lat,lon,score,signal,signal_type,source,status")
        .is_("phone", "null")
        .not_.is_("lat", "null")
        .in_("status", ["new", "queued"])
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )

    leads = result.data
    route = _nearest_neighbor_route(start_lat, start_lon, leads)

    # Add stop numbers
    for i, stop in enumerate(route, 1):
        stop["stop_number"] = i

    return {
        "start_address": start,
        "start_lat": start_lat,
        "start_lon": start_lon,
        "total_stops": len(route),
        "stops": route,
    }


@router.get("/leads/stats")
async def leads_stats(period: str = Query("7d", description="Period: 24h, 7d, 30d")):
    periods = {"24h": 1, "7d": 7, "30d": 30}
    days = periods.get(period, 7)
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    sb = get_supabase()
    base = sb.table("leads").select("status", count="exact").gte("scraped_at", since)

    total = sb.table("leads").select("id", count="exact").gte("scraped_at", since).execute().count or 0
    queued = sb.table("leads").select("id", count="exact").eq("status", "queued").gte("scraped_at", since).execute().count or 0
    called = sb.table("leads").select("id", count="exact").eq("status", "called").gte("scraped_at", since).execute().count or 0
    booked = sb.table("leads").select("id", count="exact").eq("status", "booked").gte("scraped_at", since).execute().count or 0

    return {"period": period, "total": total, "queued": queued, "called": called, "booked": booked}


@router.post("/leads/{lead_id}/email")
async def email_lead(lead_id: str):
    from datetime import datetime, timezone
    from src.outreach.emailer import send_email
    sb = get_supabase()
    result = sb.table("leads").select("*").eq("id", lead_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = result.data[0]
    if not lead.get("email"):
        raise HTTPException(status_code=400, detail="Lead has no email address")
    ok = send_email(lead["email"], lead)
    if not ok:
        raise HTTPException(status_code=500, detail="Email failed — check EMAIL_FROM and EMAIL_APP_PASSWORD in .env")
    sb.table("leads").update({"email_sent_at": datetime.now(timezone.utc).isoformat()}).eq("id", lead_id).execute()
    return {"status": "sent", "to": lead["email"]}


@router.post("/leads/{lead_id}/sms")
async def sms_lead(lead_id: str):
    from datetime import datetime, timezone
    from src.outreach.sms import send_intro_sms
    from src.voicebot.caller import is_tcpa_window
    sb = get_supabase()
    result = sb.table("leads").select("*").eq("id", lead_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = result.data[0]
    if not lead.get("phone"):
        raise HTTPException(status_code=400, detail="Lead has no phone number")
    if not is_tcpa_window():
        raise HTTPException(status_code=400, detail="Outside TCPA window (8AM-9PM ET, Mon-Sat)")
    ok = send_intro_sms(lead)
    if not ok:
        raise HTTPException(status_code=500, detail="SMS failed — check TWILIO_* keys in .env")
    sb.table("leads").update({"sms_sent_at": datetime.now(timezone.utc).isoformat()}).eq("id", lead_id).execute()
    return {"status": "sent", "to": lead["phone"]}


@router.post("/leads/{lead_id}/call")
async def call_lead(lead_id: str):
    from src.voicebot.caller import trigger_call, is_tcpa_window
    sb = get_supabase()
    result = sb.table("leads").select("*").eq("id", lead_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = result.data[0]
    if not lead.get("phone"):
        raise HTTPException(status_code=400, detail="Lead has no phone number")
    if not is_tcpa_window():
        raise HTTPException(status_code=400, detail="Outside TCPA call window (8AM-9PM ET, Mon-Sat)")
    call = trigger_call(lead)
    if not call:
        raise HTTPException(status_code=400, detail="Call not triggered — check DNC or retry limit")
    return {"status": "calling", "vapi_call_id": call.get("id")}


@router.post("/ingest/facebook")
async def ingest_facebook():
    """Trigger the Facebook Groups scraper and run results through the pipeline."""
    from src.scrapers.facebook_groups import FacebookGroupsScraper
    scraper = FacebookGroupsScraper(max_posts_per_group=50, days_back=7)
    raw_leads = scraper.run()
    if not raw_leads:
        return {"status": "ok", "message": "No irrigation-intent posts found", "total": 0}
    result: PipelineResult = run_pipeline(raw_leads)
    return IngestResponse(
        total=result.total,
        inserted=result.inserted,
        duplicates=result.duplicates,
        discarded=result.discarded,
        queued_for_call=result.queued_for_call,
        queued_for_review=result.queued_for_review,
        errors=result.errors,
    )


@router.get("/leads")
async def list_leads(
    status: str = Query("new", description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
):
    leads = get_leads_by_status(status, limit=limit)
    return {"leads": leads, "count": len(leads)}
