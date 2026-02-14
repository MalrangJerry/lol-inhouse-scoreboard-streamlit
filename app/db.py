import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def supabase_admin() -> Client:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url.startswith("https://") or "supabase.co" not in url:
        raise RuntimeError(f"SUPABASE_URL 형식 이상: {url}")

    if len(key) < 50:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY가 너무 짧습니다. (service_role JWT를 넣었는지 확인)")

    return create_client(url, key)
