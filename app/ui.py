from __future__ import annotations
import streamlit as st
from typing import List, Dict, Any

OVERLAY_CSS = """
<style>
/* 전체 여백 제거 + 370x240 박스 */
.block-container { padding: 0 !important; }
header, footer { visibility: hidden; height: 0px; }
[data-testid="stSidebar"] { display: none; }
html, body { background: transparent !important; }
#overlay {
  width: 370px; height: 240px;
  padding: 10px 12px;
  box-sizing: border-box;
  background: rgba(10,10,10,0.65);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 12px;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  color: rgba(255,255,255,0.92);
}
.row { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 14px; font-weight: 700; letter-spacing: 0.2px; }
.score { font-size: 18px; font-weight: 800; }
.sub { font-size: 11px; opacity: 0.8; margin-top: 2px; }
.hr { height: 1px; background: rgba(255,255,255,0.10); margin: 8px 0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.team { padding: 8px; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
.teamName { font-size: 12px; font-weight: 700; opacity: 0.95; margin-bottom: 6px; }
.p { display: flex; justify-content: space-between; font-size: 11px; line-height: 1.45; opacity: 0.9; }
.badge {
  font-size: 10px; font-weight: 800;
  padding: 4px 8px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.05);
}
.flash {
  position: absolute;
  width: 370px;
  left: 0; top: 0;
  padding: 10px 12px;
  box-sizing: border-box;
}
.flashBox {
  background: rgba(0,0,0,0.75);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 14px;
  font-weight: 800;
  display: inline-block;
}
.win { color: rgba(120,255,160,0.95); }
.loss { color: rgba(255,120,120,0.95); }
.containerWrap { position: relative; width: 370px; height: 240px; }
</style>
"""

def render_overlay(session: Dict[str, Any], participants: List[Dict[str, Any]], flash_text: str | None = None, flash_is_win: bool | None = None):
    st.markdown(OVERLAY_CSS, unsafe_allow_html=True)

    a = [p for p in participants if p["team"] == "A"]
    b = [p for p in participants if p["team"] == "B"]

    def team_block(team_name: str, plist: List[Dict[str, Any]]):
        lines = ""
        for p in plist:
            lines += f"""
            <div class="p">
              <span>{p['real_name']}</span>
              <span>{p['wins']}W {p['losses']}L</span>
            </div>
            """
        return f"""
        <div class="team">
          <div class="teamName">{team_name}</div>
          {lines}
        </div>
        """

    flash_html = ""
    if flash_text:
        cls = "win" if flash_is_win else "loss"
        flash_html = f"""
        <div class="flash">
          <div class="flashBox {cls}">{flash_text}</div>
        </div>
        """

    html = f"""
    <div class="containerWrap">
      {flash_html}
      <div id="overlay">
        <div class="row">
          <div>
            <div class="title">{session['name']}</div>
            <div class="sub">Solo Ranked (420) · 세션 시작 이후 집계</div>
          </div>
          <div class="badge">LIVE</div>
        </div>
        <div class="hr"></div>
        <div class="row">
          <div class="score">{session['team_a_wins']} : {session['team_b_wins']}</div>
          <div class="sub">{session['team_a_name']} vs {session['team_b_name']}</div>
        </div>
        <div class="hr"></div>
        <div class="grid">
          {team_block(session['team_a_name'], a)}
          {team_block(session['team_b_name'], b)}
        </div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
