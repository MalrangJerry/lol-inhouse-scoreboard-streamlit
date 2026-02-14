from __future__ import annotations
import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def supabase_admin() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
