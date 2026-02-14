import time
from datetime import datetime, timezone
from dateutil import parser as dtparser

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.db import supabase_admin
from app.logic import load_session, load_participants, tick_session_auto
from app.ui import render_view_roster, render_view_score, render_popup_result

st.set_page_config(page_title="Overlay", layout="centered")

session_id = st.query_params.get("session", "")
if not session_id:
    st.error("session 파라미터가 필요합니다. 예: /Overlay?session=xxxx")
    st.stop()

# ================= 설정 =================
ROTATE_SECONDS = 8        # 화면 A/B 전환 주기
POPUP_SECONDS = 4.0       # 팝업 유지 시간

AUTO_TICK = True          # 자동 집계 활성화
TICK_EVERY = 15           # 15초마다 라운드로빈 tick (10명 기준 1분 내 1바퀴)

# ================= 상태 =================

if "last_event_at" not in st.session_state:
    # 오버레이 시작 이전 이벤트는 무시
    st.session_state["last_event_at"] = datetime.now(timezone.utc)

if "popup_until" not in st.session_state:
    st.session_state["popup_until"] = 0.0
if "popup_name" not in st.session_state:
    st.session_state["popup_name"] = ""
if "popup_is_win" not in st.session_state:
    st.session_state["popup_is_win"] = False
if "popup_kda" not in st.session_state:
    st.session_state["popup_kda"] = None

if "last_tick_at" not in st.session_state:
    st.session_state["last_tick_at"] = 0.0

now = time.time()

# ================= 자동 새로고침 =================
refresh_ms = 500 if now < st.session_state["popup_until"] else 2000
st_autorefresh(interval=refresh_ms, key="overlay_refresh")

# ================= 자동 집계 (라운드로빈) =================
if AUTO_TICK and (now - st.session_state["last_tick_at"] >= TICK_EVERY):
    st.session_state["last_tick_at"] = now
    try:
        tick_session_auto(session_id)
    except Exception:
        # 방송 중 절대 죽지 않도록 무시
        pass

# ================= 데이터 로드 =================
try:
    session = load_session(session_id)
    participants = load_participants(session_id)
except Exception:
    st.stop()

sb = supabase_admin()

# ================= 최신 이벤트 1개만 체크 =================
try:
    ev = (
        sb.table("events")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
except Exception:
    ev = None

latest = (ev.data or [None])[0] if ev else None

if latest:
    try:
        latest_time = dtparser.isoparse(latest["created_at"]).astimezone(timezone.utc)

        if latest_time > st.session_state["last_event_at"]:
            st.session_state["last_event_at"] = latest_time

            is_win = latest["result"] == "WIN"
            st.session_state["popup_is_win"] = is_win
            st.session_state["popup_name"] = latest["real_name"]
            st.session_state["popup_kda"] = latest.get("kda_text")
            st.session_state["popup_until"] = time.time() + POPUP_SECONDS
    except Exception:
        pass

# ================= 화면 A/B 번갈아 표시 =================
mode = int(time.time() // ROTATE_SECONDS) % 2  # 0: roster, 1: score

if mode == 0:
    render_view_roster(session, participants)
else:
    render_view_score(session)

# ================= 팝업 =================
if time.time() < st.session_state["popup_until"]:
    render_popup_result(
        real_name=st.session_state["popup_name"],
        is_win=st.session_state["popup_is_win"],
        kda_text=st.session_state["popup_kda"],
        extra_text="방금 종료된 경기 결과"
    )
