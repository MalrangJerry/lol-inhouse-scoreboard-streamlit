# app/riot.py
from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, List, Optional

import streamlit as st
import requests


def _riot_api_key() -> str:
    # Streamlit secrets 우선, 없으면 환경변수
    key = st.secrets.get("RIOT_API_KEY", None) or os.getenv("RIOT_API_KEY", "")
    if not key or not key.startswith("RGAPI-"):
        raise RuntimeError("RIOT_API_KEY가 없거나 형식이 이상합니다. (Streamlit Secrets에 RGAPI-... 확인)")
    return key


def _region() -> str:
    # match-v5 / account-v1은 'regional routing'을 씀: asia / americas / europe
    region = (st.secrets.get("RIOT_REGION", None) or os.getenv("RIOT_REGION", "asia")).strip().lower()
    if region not in ("asia", "americas", "europe"):
        raise RuntimeError("RIOT_REGION은 asia/americas/europe 중 하나여야 합니다. (KR이면 보통 asia)")
    return region


def _headers() -> Dict[str, str]:
    return {"X-Riot-Token": _riot_api_key()}


def _base_url() -> str:
    return f"https://{_region()}.api.riotgames.com"


def _get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    r = requests.get(url, headers=_headers(), params=params, timeout=12)
    # Riot는 에러 시에도 json을 주지만, 아닐 수도 있어서 방어
    if r.status_code != 200:
        try:
            j = r.json()
        except Exception:
            j = {"status": {"status_code": r.status_code, "message": r.text[:200]}}
        raise RuntimeError(f"Riot API 실패 {r.status_code}: {j}")
    return r.json()


def get_account_by_riot_id(game_name: str, tag_line: str) -> Dict[str, Any]:
    """
    Riot Account-V1 (regional routing)
    GET /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
    """
    # ✅ 공백/한글/특수문자 URL 인코딩 필수
    gn = urllib.parse.quote(game_name.strip(), safe="")
    tl = urllib.parse.quote(tag_line.strip(), safe="")
    url = f"{_base_url()}/riot/account/v1/accounts/by-riot-id/{gn}/{tl}"
    return _get_json(url)


def get_match_ids_by_puuid(puuid: str, start_time_sec: int, count: int = 20) -> List[str]:
    """
    Match-V5 (regional routing)
    GET /lol/match/v5/matches/by-puuid/{puuid}/ids?startTime=...&count=...&queue=420
    """
    pu = urllib.parse.quote(puuid, safe="")
    url = f"{_base_url()}/lol/match/v5/matches/by-puuid/{pu}/ids"
    params = {
        "startTime": int(start_time_sec),
        "count": int(count),
        # ✅ 여기서도 솔랭(420)로 최대한 필터링
        "queue": 420,
    }
    return _get_json(url, params=params)


def get_match(match_id: str) -> Dict[str, Any]:
    """
    Match-V5 detail (regional routing)
    GET /lol/match/v5/matches/{matchId}
    """
    mid = urllib.parse.quote(match_id, safe="")
    url = f"{_base_url()}/lol/match/v5/matches/{mid}"
    return _get_json(url)
