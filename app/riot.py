from __future__ import annotations
import streamlit as st
import requests
from typing import Any, Dict, List

def _headers():
    return {"X-Riot-Token": st.secrets["RIOT_API_KEY"]}

def get_account_by_riot_id(game_name: str, tag_line: str) -> Dict[str, Any]:
    region = st.secrets["RIOT_REGION"]
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{requests.utils.quote(game_name)}/{requests.utils.quote(tag_line)}"
    r = requests.get(url, headers=_headers(), timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Riot account lookup failed: {r.status_code} {r.text}")
    return r.json()

def get_match_ids_by_puuid(puuid: str, start_time_sec: int, count: int = 20) -> List[str]:
    region = st.secrets["RIOT_REGION"]
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&startTime={start_time_sec}"
    r = requests.get(url, headers=_headers(), timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Riot match ids failed: {r.status_code} {r.text}")
    return r.json()

def get_match(match_id: str) -> Dict[str, Any]:
    region = st.secrets["RIOT_REGION"]
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    r = requests.get(url, headers=_headers(), timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Riot match get failed: {r.status_code} {r.text}")
    return r.json()
