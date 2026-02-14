from streamlit_autorefresh import st_autorefresh
from __future__ import annotations
import streamlit as st
import time
from datetime import datetime
from dateutil import parser as dtparser

from app.db import supabase_admin
from app.logic import load_session, load_participants, tick_session
from app.ui import render_view_roster, render_view_score, render_popup_result

st.set_page_config(page_title="Overlay", layout="centered")

session_id = st.query_params.get("session", "")
if not session_id:
    st.error("session 파라미터가 필요합니다. 예: /Overlay?session=xxxx-uuid")
    st.stop()

# ====== 설정 ======
ROTATE_SECONDS = 8       # 화면 A/B 전환 주기
POPUP_SECONDS = 4.0      # 승/패 팝업 유지 시간(3~5초 중 4초)
AUTO_TICK = True         # 오버레이가 켜져 있을 때 자동 집계(간단 운영용)
TICK_EVERY = 30          # tick 호출 주기(초)

# ====== 상태 ======
if "last_event_at" not in st.session_state:
    st.session_state["last_event_at"] = None  # datetime
if "popup_until" not in st.session_state:
    st.session_state["popup_until"] = 0.0
if "popup_name" not in st.session_state:
    st.session_state["popup_name"] = ""
if "popup_is_win" not in st.session_state:
    st.session_state["popup_is_win"] = False
if "last_tick_at" not in st.session_state:
    st.session_state["last_tick_at"] = 0.0

now = time.time()

# ====== 리프레시 주기: 팝업 중이면 빠르게, 아니면 느리게 ======
refresh_ms = 500 if now < st.session_state["popup_until"] else 2000
st_autorefresh(interval=refresh_ms, key="overlay_refresh")

# ====== (옵션) 자동 Tick ======
if AUTO_TICK:
    if now - st.session_state["last_tick_at"] >= TICK_EVERY:
        st.session_state["last_tick_at"] = now
        try:
            tick_session(session_id)
        except Exception:
            # 방송 중 화면이 죽지 않게 조용히 무시(원하면 로그 출력 가능)
            pass

sb = supabase_admin()

# ====== 데이터 로드 ======
session = load_session(session_id)
participants = load_participants(session_id)

# ====== 새 이벤트 감지 (events 테이블에서 created_at 기준) ======
ev = (
    sb.table("events")
    .select("*")
    .eq("session_id", session_id)
    .order("created_at", desc=True)
    .limit(20)
    .execute()
)
events = ev.data or []

last_seen = st.session_state["last_event_at"]
newest = None

# 오래된 -> 최신 순으로 돌며 last_seen 이후 첫 이벤트 찾기
for e in reversed(events):
    t = dtparser.isoparse(e["created_at"])
    if last_seen is None or t > last_seen:
        newest = e

if newest:
    t = dtparser.isoparse(newest["created_at"])
    st.session_state["last_event_at"] = t

    is_win = newest["result"] == "WIN"
    st.session_state["popup_is_win"] = is_win
    st.session_state["popup_name"] = newest["real_name"]
    st.session_state["popup_until"] = time.time() + POPUP_SECONDS

# ====== 화면 A/B 번갈아 렌더 ======
mode = int(time.time() // ROTATE_SECONDS) % 2  # 0: roster, 1: score

if mode == 0:
    render_view_roster(session, participants)
else:
    render_view_score(session)

# ====== 팝업이 있으면 위에 덮기 ======
if time.time() < st.session_state["popup_until"]:
    render_popup_result(
        real_name=st.session_state["popup_name"],
        is_win=st.session_state["popup_is_win"],
        extra_text="방금 종료된 경기 결과"
    )


