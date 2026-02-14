# app/logic.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone
import time
import random

import streamlit as st
from dateutil import parser as dtparser

from .db import supabase_admin
from .riot import get_account_by_riot_id, get_match_ids_by_puuid, get_match

QUEUE_SOLO_RANKED = 420


def _iso_to_dt(iso: str) -> datetime:
    return dtparser.isoparse(iso)


def _sb_exec(fn, retries: int = 5):
    """
    Streamlit Cloud/Supabase에서 가끔 발생하는 ReadError(EAGAIN) 같은 순간 장애 대응.
    - 짧게 대기하며 재시도
    """
    last = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last = e
            # 점진적 backoff + 약간 랜덤
            time.sleep(0.35 + i * 0.45 + random.random() * 0.2)
    raise last


def load_session(session_id: str) -> Dict[str, Any]:
    sb = supabase_admin()
    s = _sb_exec(lambda: sb.table("sessions").select("*").eq("id", session_id).single().execute())
    if not s.data:
        raise RuntimeError("세션을 찾을 수 없습니다.")
    return s.data


def load_participants(session_id: str) -> List[Dict[str, Any]]:
    sb = supabase_admin()
    p = _sb_exec(
        lambda: sb.table("session_participants")
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
    _sb_exec(lambda: sb.table("session_participants").update({"puuid": puuid}).eq("id", participant["id"]).execute())
    participant["puuid"] = puuid
    return puuid


def _already_processed(session_id: str, match_id: str, puuid: str) -> bool:
    sb = supabase_admin()
    r = _sb_exec(
        lambda: sb.table("matches")
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
        return False

    # ✅ 세션 started_at 이전에 시작한 게임은 무조건 제외 (startTime 필터 보완)
    try:
        started_dt = _iso_to_dt(session["started_at"]).astimezone(timezone.utc)
        started_ms = int(started_dt.timestamp() * 1000)
        game_start_ms = info.get("gameStartTimestamp")
        if game_start_ms and int(game_start_ms) < started_ms:
            return False
    except Exception:
        pass

    puuid = participant["puuid"]

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
        _sb_exec(
            lambda: sb.table("matches").insert(
                {
                    "session_id": session["id"],
                    "match_id": match_id,
                    "participant_puuid": puuid,
                    "result": result,
                    "team": team,
                    "game_end_ms": int(game_end),
                }
            ).execute()
        )
    except Exception:
        return False

    # 2) 개인 W/L 업데이트 + 3) 팀 승리 업데이트
    if result == "WIN":
        _sb_exec(lambda: sb.table("session_participants").update({"wins": participant["wins"] + 1}).eq("id", participant["id"]).execute())
        participant["wins"] += 1

        if team == "A":
            _sb_exec(lambda: sb.table("sessions").update({"team_a_wins": session["team_a_wins"] + 1}).eq("id", session["id"]).execute())
            session["team_a_wins"] += 1
        else:
            _sb_exec(lambda: sb.table("sessions").update({"team_b_wins": session["team_b_wins"] + 1}).eq("id", session["id"]).execute())
            session["team_b_wins"] += 1
    else:
        _sb_exec(lambda: sb.table("session_participants").update({"losses": participant["losses"] + 1}).eq("id", participant["id"]).execute())
        participant["losses"] += 1

    # 4) 이벤트 insert (오버레이 팝업용) ✅ kda_text 포함
    _sb_exec(
        lambda: sb.table("events").insert(
            {
                "session_id": session["id"],
                "real_name": participant["real_name"],
                "result": result,
                "match_id": match_id,
                "kda_text": kda_text,
            }
        ).execute()
    )

    return True


def tick_session(session_id: str) -> Tuple[int, List[str]]:
    """
    (수동 버튼용)
    Riot API를 보고 세션 DB를 최신화.
    - 세션 started_at 이후 경기만
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

            match_ids = get_match_ids_by_puuid(puuid, start_time_sec, count=20)

            for match_id in match_ids:
                if _already_processed(session_id, match_id, puuid):
                    continue

                match = get_match(match_id)

                if _insert_match_and_update(session, p, match_id, match):
                    new_count += 1

        except Exception as e:
            logs.append(f"{p.get('real_name','(unknown)')} 처리 실패: {e}")

    return new_count, logs


def tick_session_auto(session_id: str) -> Tuple[int, List[str]]:
    """
    (자동 집계용 - 라운드로빈)
    - 매 호출마다 전체 참가자를 다 돌지 않고 일부만 처리해서 429를 피함
    - 1분 이내 반영을 목표로: 10명 기준 (3명씩 / 15초) ≈ 50초 1바퀴
    """
    logs: List[str] = []
    new_count = 0

    session = load_session(session_id)
    participants = load_participants(session_id)

    started_dt = _iso_to_dt(session["started_at"]).astimezone(timezone.utc)
    start_time_sec = int(started_dt.timestamp())

    # ✅ 기본값(추천): 3명씩 처리하면 10명 기준 1분 내 1바퀴 가능
    MAX_PLAYERS_PER_TICK = 3
    # ✅ 한 사람당 match id는 적게(새 경기만 처리하면 충분)
    MATCH_ID_COUNT = 6

    n = len(participants)
    if n == 0:
        return 0, ["참가자가 없습니다."]

    # ✅ 세션별 라운드로빈 인덱스
    rr_key = f"rr_idx_{session_id}"
    if rr_key not in st.session_state:
        st.session_state[rr_key] = 0

    start_idx = st.session_state[rr_key] % n

    picked: List[Dict[str, Any]] = []
    idx = start_idx
    for _ in range(min(MAX_PLAYERS_PER_TICK, n)):
        picked.append(participants[idx])
        idx = (idx + 1) % n

    st.session_state[rr_key] = idx

    for p in picked:
        try:
            ensure_puuid(p)
            puuid = p["puuid"]

            match_ids = get_match_ids_by_puuid(puuid, start_time_sec, count=MATCH_ID_COUNT)

            for match_id in match_ids:
                if _already_processed(session_id, match_id, puuid):
                    continue

                match = get_match(match_id)

                if _insert_match_and_update(session, p, match_id, match):
                    new_count += 1

        except Exception as e:
            logs.append(f"{p.get('real_name','(unknown)')} 처리 실패: {e}")

    return new_count, logs
