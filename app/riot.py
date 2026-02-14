# app/riot.py
from __future__ import annotations

import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import streamlit as st
import requests

_SESSION = requests.Session()


def _riot_api_key() -> str:
    key = st.secrets.get("RIOT_API_KEY") or os.getenv("RIOT_API_KEY", "")
    if not key or not key.startswith("RGAPI-"):
        raise RuntimeError("RIOT_API_KEY가 없거나 형식이 이상합니다. (RGAPI-... 확인)")
    return key


def _region() -> str:
    region = (st.secrets.get("RIOT_REGION") or os.getenv("RIOT_REGION", "asia")).strip().lower()
    if region not in ("asia", "americas", "europe"):
        raise RuntimeError("RIOT_REGION은 asia/americas/europe 중 하나여야 합니다. (KR이면 asia)")
    return region


def _headers() -> Dict[str, str]:
    return {"X-Riot-Token": _riot_api_key()}


def _base_url() -> str:
    return f"https://{_region()}.api.riotgames.com"


def _get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    # ✅ 429 대응: Retry-After 있으면 그만큼, 없으면 점진 대기
    for i in range(6):
        r = _SESSION.get(url, headers=_headers(), params=params, timeout=12)

        if r.status_code == 200:
            return r.json()

        if r.status_code == 429:
            ra = r.headers.get("Retry-After", "")
            wait = int(ra) if ra.isdigit() else min(2 + i * 2, 10)
            time.sleep(wait)
            continue

        try:
            j = r.json()
        except Exception:
            j = {"status": {"status_code": r.status_code, "message": r.text[:200]}}
        raise RuntimeError(f"Riot API 실패 {r.status_code}: {j}")

    raise RuntimeError("Riot API 429: 재시도 초과")


def get_account_by_riot_id(game_name: str, tag_line: str) -> Dict[str, Any]:
    gn = urllib.parse.quote(game_name.strip(), safe="")
    tl = urllib.parse.quote(tag_line.strip(), safe="")
    url = f"{_base_url()}/riot/account/v1/accounts/by-riot-id/{gn}/{tl}"
    return _get_json(url)


def get_match_ids_by_puuid(puuid: str, start_time_sec: int, count: int = 8) -> List[str]:
    pu = urllib.parse.quote(puuid, safe="")
    url = f"{_base_url()}/lol/match/v5/matches/by-puuid/{pu}/ids"
    params = {"startTime": int(start_time_sec), "count": int(count), "queue": 420}
    return _get_json(url, params=params)


def get_match(match_id: str) -> Dict[str, Any]:
    mid = urllib.parse.quote(match_id, safe="")
    url = f"{_base_url()}/lol/match/v5/matches/{mid}"
    return _get_json(url)
