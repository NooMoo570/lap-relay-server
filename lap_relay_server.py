from typing import Dict, Optional
import time

from fastapi import FastAPI, Query
from pydantic import BaseModel


app = FastAPI()

# Fuel系と完全分離
lap_store: Dict[str, Dict[str, dict]] = {}

LAP_TTL_SECONDS = 30
LAP_CLEANUP_INTERVAL_SECONDS = 10

lap_last_cleanup_at: Dict[str, float] = {}


def normalize_team_key(value: str) -> str:
    return str(value).strip().upper()


class LapData(BaseModel):
    team_key: str
    name: str
    ave: Optional[float] = None
    best: Optional[float] = None
    stdev: Optional[float] = None
    lap_count: int
    pitout_lap_count: int
    timestamp: float
    setup_name: Optional[str] = None
    setup_name_raw: Optional[str] = None


def cleanup_lap_team(team_key: str, stale_seconds: int = LAP_TTL_SECONDS) -> None:
    team_data = lap_store.get(team_key)
    if not team_data:
        return

    now = time.time()
    delete_names = []

    for driver_name, item in team_data.items():
        ts = float(item.get("server_received_at", 0)) if item.get("server_received_at") is not None else 0
        if now - ts > stale_seconds:
            delete_names.append(driver_name)

    for name in delete_names:
        team_data.pop(name, None)

    if not team_data:
        lap_store.pop(team_key, None)


def cleanup_lap_team_if_needed(team_key: str, interval_sec: int = LAP_CLEANUP_INTERVAL_SECONDS) -> None:
    now = time.time()
    last = lap_last_cleanup_at.get(team_key, 0)

    if now - last >= interval_sec:
        cleanup_lap_team(team_key)
        lap_last_cleanup_at[team_key] = now


@app.get("/")
def root():
    for tk in list(lap_store.keys()):
        cleanup_lap_team_if_needed(tk)

    return {
        "ok": True,
        "message": "lap relay server running",
        "lap_teams": list(lap_store.keys()),
        "lap_ttl_seconds": LAP_TTL_SECONDS,
        "lap_cleanup_interval_seconds": LAP_CLEANUP_INTERVAL_SECONDS,
    }


@app.post("/lap/update")
def lap_update(data: LapData):
    team_key = normalize_team_key(data.team_key)
    driver_name = str(data.name).strip()

    if not team_key:
        return {"ok": False, "error": "team_key is required"}

    if not driver_name:
        return {"ok": False, "error": "name is required"}

    if team_key not in lap_store:
        lap_store[team_key] = {}

    stored_row = {
        "ave": float(data.ave) if data.ave is not None else None,
        "best": float(data.best) if data.best is not None else None,
        "stdev": float(data.stdev) if data.stdev is not None else None,
        "lap_count": int(data.lap_count),
        "pitout_lap_count": int(data.pitout_lap_count),
        "timestamp": float(data.timestamp),
        "setup_name": str(data.setup_name).strip() if data.setup_name is not None else None,
        "setup_name_raw": str(data.setup_name_raw).strip() if data.setup_name_raw is not None else None,
        "server_received_at": time.time(),
    }

    lap_store[team_key][driver_name] = stored_row

    cleanup_lap_team_if_needed(team_key)

    return {
        "ok": True,
        "team_key": team_key,
        "name": driver_name,
        "ave": stored_row["ave"],
        "best": stored_row["best"],
        "stdev": stored_row["stdev"],
        "lap_count": stored_row["lap_count"],
        "pitout_lap_count": stored_row["pitout_lap_count"],
        "setup_name": stored_row["setup_name"],
        "setup_name_raw": stored_row["setup_name_raw"],
    }


@app.get("/lap/all")
def lap_all(team_key: str = Query(...)):
    team_key = normalize_team_key(team_key)

    if not team_key:
        return {"ok": False, "error": "team_key is required"}

    cleanup_lap_team_if_needed(team_key)

    team_data = lap_store.get(team_key, {})
    result = {}

    for driver_name, item in team_data.items():
        result[driver_name] = {
            "ave": item.get("ave"),
            "best": item.get("best"),
            "stdev": item.get("stdev"),
            "lap_count": item.get("lap_count"),
            "pitout_lap_count": item.get("pitout_lap_count"),
            "timestamp": item.get("timestamp"),
            "setup_name": item.get("setup_name"),
            "setup_name_raw": item.get("setup_name_raw"),
        }

    return result


@app.get("/lap/teams")
def lap_teams():
    for tk in list(lap_store.keys()):
        cleanup_lap_team_if_needed(tk)

    return {
        "ok": True,
        "teams": list(lap_store.keys()),
        "lap_ttl_seconds": LAP_TTL_SECONDS,
        "lap_cleanup_interval_seconds": LAP_CLEANUP_INTERVAL_SECONDS,
    }
