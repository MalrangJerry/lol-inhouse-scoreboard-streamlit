from __future__ import annotations
import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def supabase_admin() -> Client:
    # Streamlit Secrets에 아래 키들이 있어야 함:
    # SUPABASE_URL
    # SUPABASE_SERVICE_ROLE_KEY  (Supabase의 sb_secret_... 키)
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
