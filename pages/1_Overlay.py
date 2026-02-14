from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone
from dateutil import parser as dtparser

from app.db import supabase_admin
from app.logic import load_session, load_participants, tick_session
from app.ui import render_overlay

def _dt(s: str) -> datetime:
    return dtparser.isoparse(s)

st.set_page_config(page_title="Overlay", layout="centered")

# query param: ?session=uuid
session_id = st.query_params.get("session", "")
if not session_id:
    st.error("session 파라미터가 필요합니다. 예: /Overlay?session=xxxx-uuid")
    st.stop()

# 오버레이용: 상단 여백 최소화
st.markdown(
    """
    <style>
    .block-container { padding-top: 0.2rem; padding-bottom: 0rem; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---- 상태: 마지막 본 이벤트 시각(뷰어별)
if "last_event_at" not in st.session_state:
    st.session_state["last_event_at"] = None  # datetime
if "flash_until" not in st.session_state:
    st.session_state["flash_until"] = 0.0
if "flash_text" not in st.session_state:
    st.session_state["flash_text"] = None
if "flash_is_win" not in st.session_state:
    st.session_state["flash_is_win"] = None

# ---- Tick: Streamlit에서 서버 스케줄러가 없으니, 오버레이 페이지에서 주기적으로 tick 실행 가능(옵션)
# 운영 정책: 오버레이를 항상 켜둘 거면 이게 가장 간단함
AUTO_TICK = True

# ---- 오버레이 이벤트 표시 중이면 1초 리프레시, 아니면 30초
import time
now = time.time()
refresh_ms = 1000 if now < st.session_state["flash_until"] else 30000
st.experimental_set_query_params(session=session_id)
st.autorefresh(interval=refresh_ms, key="overlay_refresh")

# ---- (옵션) tick 실행
if AUTO_TICK and refresh_ms == 30000:
    # 평소 30초 주기 때만 tick
    try:
        tick_session(session_id)
    except Exception:
        # 오버레이는 죽지 않게(방송 중)
        pass

sb = supabase_admin()

# ---- 데이터 로드
session = load_session(session_id)
participants = load_participants(session_id)

# ---- 새 이벤트 감지 (최신 20개만)
ev = sb.table("events").select("*").eq("session_id", session_id).order("created_at", desc=True).limit(20).execute()
events = ev.data or []

last_seen = st.session_state["last_event_at"]
newest_event = None
for e in reversed(events):  # 오래된->최신 순으로 검사
    t = _dt(e["created_at"])
    if last_seen is None or t > last_seen:
        newest_event = e

if newest_event:
    t = _dt(newest_event["created_at"])
    st.session_state["last_event_at"] = t
    # 4초 표시
    st.session_state["flash_until"] = time.time() + 4.0
    is_win = newest_event["result"] == "WIN"
    st.session_state["flash_is_win"] = is_win
    st.session_state["flash_text"] = f"{newest_event['real_name']} {'승리' if is_win else '패배'}"

flash_text = None
flash_is_win = None
if time.time() < st.session_state["flash_until"]:
    flash_text = st.session_state["flash_text"]
    flash_is_win = st.session_state["flash_is_win"]

render_overlay(session, participants, flash_text=flash_text, flash_is_win=flash_is_win)
