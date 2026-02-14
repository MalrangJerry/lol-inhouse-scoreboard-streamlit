from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone
from postgrest.exceptions import APIError

from app.db import supabase_admin
from app.parse import parse_line
from app.logic import tick_session, load_session, load_participants

st.set_page_config(page_title="LOL 내전 전광판", layout="centered")

st.title("LOL 5:5 솔랭 내전 전광판 (Supabase + Streamlit)")

sb = supabase_admin()

with st.expander("1) 새 세션 만들기", expanded=True):
    name = st.text_input("세션 이름", value="내전")
    col1, col2 = st.columns(2)
    team_a = col1.text_input("팀 A 이름", value="TEAM A")
    team_b = col2.text_input("팀 B 이름", value="TEAM B")

    st.caption("참가자 10명 입력: 각 줄에 `본명,게임닉#태그`")
    st.caption("예: 홍길동,Hide on bush#KR1")
    raw = st.text_area("참가자 리스트", height=220, value="")

    colA, colB = st.columns(2)
    with colA:
        st.caption("팀 배정: 앞 5명 = A, 뒤 5명 = B (기본)")
    with colB:
        st.caption("또는 아래 체크로 교체 가능")

if st.button("세션 생성", type="primary"):
    lines = [x for x in raw.splitlines() if x.strip()]
    total = len(lines)

    if total < 2:
        st.error("최소 2명 이상이어야 합니다.")
    elif total % 2 != 0:
        st.error("참가자 수는 짝수여야 합니다.")
    else:
        try:
            s = sb.table("sessions").insert({
                "name": name,
                "team_a_name": team_a,
                "team_b_name": team_b,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "team_a_wins": 0,
                "team_b_wins": 0,
            }).execute()

            session_id = s.data[0]["id"]

            half = total // 2

            for i, line in enumerate(lines):
                info = parse_line(line)
                team = "A" if i < half else "B"

                sb.table("session_participants").insert({
                    "session_id": session_id,
                    "real_name": info["real_name"],
                    "riot_game_name": info["game_name"],
                    "riot_tag_line": info["tag_line"],
                    "team": team,
                }).execute()

        except Exception as e:
            st.exception(e)
            st.stop()

        st.success(f"세션 생성 완료: {session_id}")

            st.info("오버레이 페이지는 왼쪽 Pages → Overlay 또는 아래 링크 사용")
            st.code(f"/Overlay?session={session_id}")

st.divider()

st.subheader("2) 기존 세션 불러오기 / Tick (Riot 집계)")
session_id = st.text_input("세션 ID", value=st.query_params.get("session", ""))

if session_id:
    try:
        session = load_session(session_id)
        participants = load_participants(session_id)

        st.write(f"세션: **{session['name']}**")
        st.write(f"팀명: {session['team_a_name']} vs {session['team_b_name']}")
        st.write(f"점수: **{session['team_a_wins']} : {session['team_b_wins']}**")

        c1, c2 = st.columns(2)
        if c1.button("팀 이름 변경"):
            new_a = c1.text_input("새 팀 A 이름", value=session["team_a_name"], key="newa")
            new_b = c2.text_input("새 팀 B 이름", value=session["team_b_name"], key="newb")
            if st.button("저장"):
                sb.table("sessions").update({"team_a_name": new_a, "team_b_name": new_b}).eq("id", session_id).execute()
                st.success("저장 완료. 새로고침하세요.")

        if st.button("지금 집계(Tick) 실행"):
            with st.spinner("Riot API 조회 중..."):
                new_count, logs = tick_session(session_id)
            st.success(f"신규 집계 {new_count}건 처리")
            if logs:
                st.warning("\n".join(logs))

        st.caption("OBS 오버레이: Pages → Overlay에서 session 파라미터로 접근")
        st.code(f"/Overlay?session={session_id}")

    except Exception as e:
        st.error(str(e))
else:
    st.info("세션 ID를 넣으면 관리/집계할 수 있어요.")

