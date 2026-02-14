from __future__ import annotations
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone
from dateutil import parser as dtparser

from .db import supabase_admin
from .riot import get_account_by_riot_id, get_match_ids_by_puuid, get_match

QUEUE_SOLO_RANKED = 420

def _iso_to_dt(iso: str) -> datetime:
    # Supabase timestamptz -> aware datetime
    return dtparser.isoparse(iso)

def load_session(session_id: str) -> Dict[str, Any]:
    sb = supabase_admin()
    s = sb.table("sessions").select("*").eq("id", session_id).single().execute()
    if not s.data:
        raise RuntimeError("세션을 찾을 수 없습니다.")
    return s.data

def load_participants(session_id: str) -> List[Dict[str, Any]]:
    sb = supabase_admin()
    p = sb.table("session_participants").select("*").eq("session_id", session_id).order("team").order("real_name").execute()
    return p.data or []

def ensure_puuid(participant: Dict[str, Any]) -> str:
    if participant.get("puuid"):
        return participant["puuid"]
    acc = get_account_by_riot_id(participant["riot_game_name"], participant["riot_tag_line"])
    puuid = acc["puuid"]
    sb = supabase_admin()
    sb.table("session_participants").update({"puuid": puuid}).eq("id", participant["id"]).execute()
    participant["puuid"] = puuid
    return puuid

def _already_processed(session_id: str, match_id: str, puuid: str) -> bool:
    sb = supabase_admin()
    r = sb.table("matches").select("id").eq("session_id", session_id).eq("match_id", match_id).eq("participant_puuid", puuid).limit(1).execute()
    return bool(r.data)

def _insert_match_and_update(session: Dict[str, Any], participant: Dict[str, Any], match_id: str, match: Dict[str, Any]) -> None:
    info = match["info"]
    if info.get("queueId") != QUEUE_SOLO_RANKED:
        return

    game_end = info.get("gameEndTimestamp")
    if not game_end:
        # 아직 끝나지 않은 게임이면 스킵
        return

    puuid = participant["puuid"]
    me = next((x for x in info["participants"] if x["puuid"] == puuid), None)
    if not me:
        return

    result = "WIN" if me["win"] else "LOSS"
    team = participant["team"]
    sb = supabase_admin()

    # 1) matches insert (unique로 중복 방지)
    try:
        sb.table("matches").insert({
            "session_id": session["id"],
            "match_id": match_id,
            "participant_puuid": puuid,
            "result": result,
            "team": team,
            "game_end_ms": int(game_end),
        }).execute()
    except Exception:
        # unique 충돌 등 -> 안전하게 무시
        return

    # 2) 개인 W/L 업데이트
    if result == "WIN":
        sb.table("session_participants").update({"wins": participant["wins"] + 1}).eq("id", participant["id"]).execute()
        participant["wins"] += 1
        # 3) 팀 승리 +1
        if team == "A":
            sb.table("sessions").update({"team_a_wins": session["team_a_wins"] + 1}).eq("id", session["id"]).execute()
            session["team_a_wins"] += 1
        else:
            sb.table("sessions").update({"team_b_wins": session["team_b_wins"] + 1}).eq("id", session["id"]).execute()
            session["team_b_wins"] += 1
    else:
        sb.table("session_participants").update({"losses": participant["losses"] + 1}).eq("id", participant["id"]).execute()
        participant["losses"] += 1

    # 4) 이벤트 insert (오버레이용)
    sb.table("events").insert({
        "session_id": session["id"],
        "real_name": participant["real_name"],
        "result": result,
        "match_id": match_id,
    }).execute()

def tick_session(session_id: str) -> Tuple[int, List[str]]:
    """
    Riot API를 보고 세션 DB를 최신화.
    return: (처리된 신규 경기 수, 로그 메시지)
    """
    logs: List[str] = []
    session = load_session(session_id)
    participants = load_participants(session_id)

    started_at = session["started_at"]
    started_dt = _iso_to_dt(started_at).astimezone(timezone.utc)
    start_time_sec = int(started_dt.timestamp())

    new_count = 0

    for p in participants:
        try:
            ensure_puuid(p)
            puuid = p["puuid"]
            ids = get_match_ids_by_puuid(puuid, start_time_sec, count=20)

            for match_id in ids:
                if _already_processed(session_id, match_id, puuid):
                    continue
                match = get_match(match_id)
                before = (session["team_a_wins"], session["team_b_wins"], p["wins"], p["losses"])
                _insert_match_and_update(session, p, match_id, match)
                after = (session["team_a_wins"], session["team_b_wins"], p["wins"], p["losses"])
                if after != before:
                    new_count += 1

        except Exception as e:
            logs.append(f"{p['real_name']} 처리 실패: {e}")

    return new_count, logs
