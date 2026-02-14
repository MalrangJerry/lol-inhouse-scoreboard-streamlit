# app/logic.py
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
    p = (
        sb.table("session_participants")
        .select("*")
        .eq("session_id", session_id)
        .order("team")
        .order("real_name")
        .execute()
    )
    return p.data or []


def ensure_puuid(participant: Dict[str, Any]) -> str:
    """
    participant.puuid가 없으면 Riot Account API로 조회해 저장.
    """
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
    r = (
        sb.table("matches")
        .select("id")
        .eq("session_id", session_id)
        .eq("match_id", match_id)
        .eq("participant_puuid", puuid)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def _insert_match_and_update(
    session: Dict[str, Any],
    participant: Dict[str, Any],
    match_id: str,
    match: Dict[str, Any],
) -> bool:
    """
    신규 match를 DB에 반영.
    성공적으로 '집계(승/패 + 팀승 + 이벤트)'가 반영되면 True, 아니면 False.
    """
    info = match.get("info", {})
    if info.get("queueId") != QUEUE_SOLO_RANKED:
        return False

    game_end = info.get("gameEndTimestamp")
    if not game_end:
        # 게임이 아직 끝나지 않으면 스킵
        return False

    puuid = participant["puuid"]

    # match-v5 participants에는 kills/deaths/assists, win 등이 들어있음
    me = next((x for x in info.get("participants", []) if x.get("puuid") == puuid), None)
    if not me:
        return False

    result = "WIN" if bool(me.get("win")) else "LOSS"

    # ✅ KDA 추출
    kills = int(me.get("kills", 0))
    deaths = int(me.get("deaths", 0))
    assists = int(me.get("assists", 0))
    kda_text = f"KDA: {kills}/{deaths}/{assists}"

    team = participant["team"]
    sb = supabase_admin()

    # 1) matches insert (unique 제약으로 중복 방지)
    try:
        sb.table("matches").insert(
            {
                "session_id": session["id"],
                "match_id": match_id,
                "participant_puuid": puuid,
                "result": result,
                "team": team,
                "game_end_ms": int(game_end),
            }
        ).execute()
    except Exception:
        # unique 충돌 등 -> 이미 처리된 케이스로 간주
        return False

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

    # 4) 이벤트 insert (오버레이 팝업용) ✅ kda_text 포함
    sb.table("events").insert(
        {
            "session_id": session["id"],
            "real_name": participant["real_name"],
            "result": result,
            "match_id": match_id,
            "kda_text": kda_text,  # ✅ 추가
        }
    ).execute()

    return True


def tick_session(session_id: str) -> Tuple[int, List[str]]:
    """
    Riot API를 보고 세션 DB를 최신화.
    - 세션 started_at 이후의 경기만
    - 솔랭(420)만
    - 중복 집계 방지(matches unique)
    return: (신규 반영된 경기 수, 로그 메시지 리스트)
    """
    logs: List[str] = []

    session = load_session(session_id)
    participants = load_participants(session_id)

    started_dt = _iso_to_dt(session["started_at"]).astimezone(timezone.utc)
    start_time_sec = int(started_dt.timestamp())

    new_count = 0

    for p in participants:
        try:
            ensure_puuid(p)
            puuid = p["puuid"]

            # 최근 20개만 조회(세션 시작 이후)
            match_ids = get_match_ids_by_puuid(puuid, start_time_sec, count=20)

            for match_id in match_ids:
                if _already_processed(session_id, match_id, puuid):
                    continue

                match = get_match(match_id)

                applied = _insert_match_and_update(session, p, match_id, match)
                if applied:
                    new_count += 1

        except Exception as e:
            logs.append(f"{p.get('real_name','(unknown)')} 처리 실패: {e}")

    return new_count, logs
