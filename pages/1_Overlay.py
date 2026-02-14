import time
from datetime import datetime, timezone
from dateutil import parser as dtparser

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.db import supabase_admin
from app.logic import load_session, load_participants
from app.ui import render_view_roster, render_view_score, render_popup_result

st.set_page_config(page_title="Overlay", layout="centered")

session_id = st.query_params.get("session", "")
if not session_id:
    st.error("session 파라미터가 필요합니다. 예: /Overlay?session=xxxx")
    st.stop()

# ====== 설정 ======
ROTATE_SECONDS = 8       # 화면 A/B 전환 주기
POPUP_SECONDS = 4.0      # 팝업 유지 시간

# ====== 상태 ======
if "last_event_at" not in st.session_state:
    st.session_state["last_event_at"] = datetime.now(timezone.utc)

if "popup_until" not in st.session_state:
    st.session_state["popup_until"] = 0.0
if "popup_name" not in st.session_state:
    st.session_state["popup_name"] = ""
if "popup_is_win" not in st.session_state:
    st.session_state["popup_is_win"] = False
if "popup_kda" not in st.session_state:
    st.session_state["popup_kda"] = None

now = time.time()

# ====== 리프레시 ======
refresh_ms = 500 if now < st.session_state["popup_until"] else 2000
st_autorefresh(interval=refresh_ms, key="overlay_refresh")

sb = supabase_admin()

# ====== 데이터 로드 (읽기 전용) ======
try:
    session = load_session(session_id)
    participants = load_participants(session_id)
except Exception:
    st.stop()

# ====== 최신 이벤트 1개 확인 → 새 이벤트면 팝업 ======
try:
    ev = (
        sb.table("events")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    latest = (ev.data or [None])[0]
except Exception:
    latest = None

if latest:
    try:
        latest_time = dtparser.isoparse(latest["created_at"]).astimezone(timezone.utc)
        if latest_time > st.session_state["last_event_at"]:
            st.session_state["last_event_at"] = latest_time
            st.session_state["popup_is_win"] = (latest["result"] == "WIN")
            st.session_state["popup_name"] = latest["real_name"]
            st.session_state["popup_kda"] = latest.get("kda_text")
            st.session_state["popup_until"] = time.time() + POPUP_SECONDS
    except Exception:
        pass

# ====== 화면 A/B 번갈아 렌더 ======
mode = int(time.time() // ROTATE_SECONDS) % 2  # 0: roster, 1: score
if mode == 0:
    render_view_roster(session, participants)
else:
    render_view_score(session)

# ====== 팝업 ======
if time.time() < st.session_state["popup_until"]:
    render_popup_result(
        real_name=st.session_state["popup_name"],
        is_win=st.session_state["popup_is_win"],
        kda_text=st.session_state["popup_kda"],
        extra_text="방금 종료된 경기 결과"
    )
