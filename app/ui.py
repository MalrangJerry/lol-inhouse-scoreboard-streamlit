from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from typing import List, Dict, Any

BASE_CSS = """
<style>
.block-container { padding: 0 !important; }
header, footer { visibility: hidden; height: 0px; }
[data-testid="stSidebar"] { display: none; }
html, body { background: transparent !important; }

.wrap { position: relative; width: 370px; height: 240px; }

.card {
  width: 370px; height: 240px;
  box-sizing: border-box;
  padding: 10px 12px;
  background: rgba(10,10,10,0.70);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 14px;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  color: rgba(255,255,255,0.92);
}

.row { display:flex; justify-content:space-between; align-items:center; }
.hr { height: 1px; background: rgba(255,255,255,0.10); margin: 8px 0; }

.title { font-size: 12px; font-weight: 800; opacity: .95; }
.sub { font-size: 10px; opacity: .75; }

.grid2 { display:grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.teamBox { padding: 8px; border: 1px solid rgba(255,255,255,0.10); border-radius: 12px; }
.teamName { font-size: 11px; font-weight: 900; margin-bottom: 6px; }
.p { display:flex; justify-content:space-between; font-size: 10px; line-height: 1.5; opacity: .92; }
.small { font-size: 10px; opacity: .7; }

.scoreBig {
  height: 160px;
  display:flex;
  align-items:center;
  justify-content:center;
  flex-direction:column;
  gap: 6px;
}
.scoreLabel { font-size: 14px; font-weight: 900; letter-spacing: .5px; opacity: .95; }
.scoreNums { font-size: 44px; font-weight: 1000; line-height: 1; }
.vs { font-size: 10px; opacity: .6; margin: 2px 0; }
.teamLine { font-size: 11px; opacity: .85; }

.badge {
  font-size: 10px; font-weight: 900;
  padding: 4px 8px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(255,255,255,0.06);
}

/* 팝업(세 번째 이미지 느낌) */
.popup {
  position: absolute;
  left: 0; top: 0;
  width: 370px; height: 240px;
  border-radius: 14px;
  display:flex;
  align-items:center;
  justify-content:center;
  flex-direction:column;
  gap: 10px;
  text-align:center;
  z-index: 10;
  border: 1px solid rgba(255,255,255,0.18);
}
.popup.win {
  background: linear-gradient(180deg, rgba(45, 185, 120, .92), rgba(20, 120, 80, .92));
}
.popup.loss {
  background: linear-gradient(180deg, rgba(255, 92, 92, .92), rgba(180, 45, 45, .92));
}
.popupTitle { font-size: 30px; font-weight: 1000; letter-spacing: 1px; }
.popupName { font-size: 18px; font-weight: 900; opacity: .95; }
.popupSub { font-size: 11px; opacity: .9; padding: 6px 10px; border-radius: 999px; background: rgba(0,0,0,.25); border: 1px solid rgba(255,255,255,.22); }
</style>
"""

def _split_teams(participants: List[Dict[str, Any]]):
    a = [p for p in participants if p["team"] == "A"]
    b = [p for p in participants if p["team"] == "B"]
    return a, b

def render_view_roster(session, participants):
    a, b = _split_teams(participants)

    def team_block(team_name, plist):
        lines = ""
        for p in plist:
            lines += f"""
              <div class="p">
                <span>{p['real_name']}</span>
                <span>{p['wins']}승 {p['losses']}패</span>
              </div>
            """
        return f"""
          <div class="teamBox">
            <div class="teamName">{team_name}</div>
            {lines}
          </div>
        """

    html = f"""
    {BASE_CSS}
    <div class="wrap">
      <div class="card">
        <div class="row">
          <div>
            <div class="title">{session['name']}</div>
            <div class="sub">팀별 개인 전적</div>
          </div>
          <div class="badge">LIVE</div>
        </div>
        <div class="hr"></div>
        <div class="grid2">
          {team_block(session['team_a_name'], a)}
          {team_block(session['team_b_name'], b)}
        </div>
      </div>
    </div>
    """
    components.html(html, height=240, width=370)



def render_view_score(session):
    html = f"""
    {BASE_CSS}
    <div class="wrap">
      <div class="card">
        <div class="row">
          <div class="title">TOTAL SCORE</div>
          <div class="badge">LIVE</div>
        </div>
        <div class="hr"></div>
        <div class="scoreBig">
          <div class="scoreNums">{session['team_a_wins']} <span class="vs">VS</span> {session['team_b_wins']}</div>
          <div class="teamLine">{session['team_a_name']}  vs  {session['team_b_name']}</div>
          <div class="small">Solo Ranked (420) · 세션 시작 이후 집계</div>
        </div>
      </div>
    </div>
    """
    components.html(html, height=240, width=370)

def render_popup_result(real_name: str, is_win: bool, extra_text: str = "방금 종료된 경기 결과"):
    cls = "win" if is_win else "loss"
    title = "승리" if is_win else "패배"
    st.markdown(
        f"""
        <div class="popup {cls}">
          <div class="popupTitle">{title}</div>
          <div class="popupName">{real_name}</div>
          <div class="popupSub">{extra_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


