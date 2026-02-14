from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone, timedelta

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.db import supabase_admin
from app.logic import tick_session_auto, load_session
from app.riot import get_account_by_riot_id

st.set_page_config(page_title="Tick Runner", layout="centered")

# ====== Riot 연결 테스트 (맨 위에서 1회 확인) ======
st.subheader("Riot 연결 테스트")
try:
    test = get_account_by_riot_id("Hide on bush", "KR1")
    st.success("✅ Riot API 정상 연결 (Account API OK)")
    # 필요하면 아래 주석 해제해서 상세 확인
    # st.json(test)
except Exception as e:
    st.error(f"❌ Riot API 실패: {e}")
    st.info("이 에러가 403이면 키 문제, 404면 Riot ID(닉/태그) 문제, 429면 호출량 문제입니다.")
    # 연결 자체가 안 되면 집계는 100% 안 되니까 여기서 중단
    st.stop()

st.divider()

# ====== 입력 ======
session_id = st.query_params.get("session", "")
if not session_id:
    st.error("session 파라미터가 필요합니다. 예: /TickRunner?session=xxxx")
    st.stop()

# ====== 설정 ======
TICK_EVERY = 15          # 15초마다 tick_session_auto 호출(라운드로빈)
LOCK_TTL_SEC = 45        # 락 유효시간(초)
REFRESH_MS = 2000        # runner 화면 리프레시

# ====== 상태 ======
if "runner_id" not in st.session_state:
    st.session_state["runner_id"] = str(uuid.uuid4())
runner_id = st.session_state["runner_id"]

if "last_tick_at" not in st.session_state:
    st.session_state["last_tick_at"] = 0.0

sb = supabase_admin()
st_autorefresh(interval=REFRESH_MS, key="tick_runner_refresh")
now = time.time()

st.title("Tick Runner (집계 전용)")
st.caption("이 페이지는 Riot API 집계를 수행합니다. Overlay는 읽기 전용으로 두세요.")
st.caption(f"Session: {session_id}")
st.caption(f"Runner ID: {runner_id}")


def try_acquire_lock(session_id: str) -> bool:
    """
    sessions.tick_lock_until이 비었거나 만료된 경우에만 락 획득.
    """
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    lock_until = (now_dt + timedelta(seconds=LOCK_TTL_SEC)).isoformat()

    r = (
        sb.table("sessions")
        .update({"tick_lock_until": lock_until, "tick_lock_owner": runner_id})
        .eq("id", session_id)
        .or_(f"tick_lock_until.is.null,tick_lock_until.lt.{now_iso}")
        .execute()
    )
    return bool(r.data)


def refresh_lock(session_id: str) -> None:
    """
    내가 락 소유자일 때만 TTL 연장(heartbeat)
    """
    now_dt = datetime.now(timezone.utc)
    lock_until = (now_dt + timedelta(seconds=LOCK_TTL_SEC)).isoformat()
    (
        sb.table("sessions")
        .update({"tick_lock_until": lock_until})
        .eq("id", session_id)
        .eq("tick_lock_owner", runner_id)
        .execute()
    )


# ====== 락 획득 시도 ======
acquired = False
lock_err = None
try:
    acquired = try_acquire_lock(session_id)
except Exception as e:
    lock_err = e
    acquired = False

if lock_err:
    st.error(f"락 획득 시도 중 에러: {lock_err}")

if not acquired:
    st.warning("다른 Tick Runner가 집계 중입니다. (이 창은 대기 상태)")
    try:
        s = load_session(session_id)
        st.caption(f"세션: {s.get('name','')} | 현재 락 소유자: {s.get('tick_lock_owner')}")
        st.caption(f"lock_until: {s.get('tick_lock_until')}")
    except Exception as e:
        st.error(f"세션 로드 실패: {e}")
    st.stop()

st.success("✅ 락 획득 성공! 이 Runner가 집계를 수행합니다.")

# ====== 락 연장(heartbeat) ======
try:
    refresh_lock(session_id)
except Exception as e:
    st.error(f"락 연장 실패: {e}")

# ====== tick 실행 ======
remain = int(max(0, TICK_EVERY - (now - st.session_state["last_tick_at"])))
st.caption(f"다음 tick까지: {remain}초 | TICK_EVERY={TICK_EVERY}s | LOCK_TTL={LOCK_TTL_SEC}s")

if now - st.session_state["last_tick_at"] >= TICK_EVERY:
    st.session_state["last_tick_at"] = now
    try:
        new_count, logs = tick_session_auto(session_id)
        st.success(f"tick 실행 완료: 신규 {new_count}건")
        st.text_area("tick logs (참가자별 실패 원인 포함)", "\n".join(logs) if logs else "(로그 없음)", height=260)
    except Exception as e:
        st.error(f"tick 자체 실패: {e}")
