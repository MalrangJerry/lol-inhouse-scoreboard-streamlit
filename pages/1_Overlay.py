import time
from datetime import datetime, timezone
from dateutil import parser as dtparser

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.db import supabase_admin
from app.logic import load_session, load_participants, tick_session
from app.ui import render_view_roster, render_view_score, render_popup_result

st.set_page_config(page_title="Overlay", layout="centered")

session_id = st.query_params.get("session", "")
if not session_id:
    st.error("session 파라미터가 필요합니다. 예: /Overlay?session=xxxx")
    st.stop()

# ====== 설정 ======
ROTATE_SECONDS = 8       # 화면 A/B 전환 주기
POPUP_SECONDS = 4.0      # 팝업 유지 시간
AUTO_TICK = True        # ✅ 처음엔 False 추천 (원인 정리 후 True로)
TICK_EVERY = 30          # tick 호출 주기(초)

# ====== 상태 ======
# ✅ 핵심: 오버레이 시작 시점 이전 이벤트는 '이미 본 것'으로 처리해서 팝업 반복 방지
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

if "last_tick_at" not in st.session_state:
    st.session_state["last_tick_at"] = 0.0

now = time.time()

# ====== 리프레시 주기 ======
# 팝업 중이면 더 자주 갱신(부드럽게), 평소엔 느리게
refresh_ms = 500 if now < st.session_state["popup_until"] else 2000
st_autorefresh(interval=refresh_ms, key="overlay_refresh")

# ====== (옵션) 자동 Tick ======
if AUTO_TICK and (now - st.session_state["last_tick_at"] >= TICK_EVERY):
    st.session_state["last_tick_at"] = now
    try:
        tick_session(session_id)
    except Exception:
        # 방송 중 화면 죽지 않게 무시
        pass

sb = supabase_admin()

# ====== 데이터 로드 ======
session = load_session(session_id)
participants = load_participants(session_id)

# ====== 최신 이벤트 1개만 확인해서 '새로운 것'이면 팝업 ======
ev = (
    sb.table("events")
    .select("*")
    .eq("session_id", session_id)
    .order("created_at", desc=True)
    .limit(1)
    .execute()
)

latest = (ev.data or [None])[0]
if latest:
    latest_time = dtparser.isoparse(latest["created_at"]).astimezone(timezone.utc)

    # ✅ last_event_at 이후에 생성된 이벤트만 "새 이벤트"로 인정
    if latest_time > st.session_state["last_event_at"]:
        st.session_state["last_event_at"] = latest_time

        is_win = latest["result"] == "WIN"
        st.session_state["popup_is_win"] = is_win
        st.session_state["popup_name"] = latest["real_name"]
        st.session_state["popup_kda"] = latest.get("kda_text")
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
        kda_text=st.session_state["popup_kda"],
        extra_text="방금 종료된 경기 결과"
    )

