# app/db.py
from __future__ import annotations

import streamlit as st
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

@st.cache_resource
def supabase_admin() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

    # ✅ httpx 타임아웃/커넥션 풀 옵션 (안정성 개선)
    options = ClientOptions(
        schema="public",
        postgrest_client_timeout=20,  # seconds
        storage_client_timeout=20,
        realtime_client_timeout=20,
    )
    return create_client(url, key, options=options)
