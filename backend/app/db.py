"""Supabase client.

The backend talks to Supabase with the secret key, which bypasses row level
security. It must never be shipped to the browser.
"""

from functools import lru_cache

from supabase import Client, create_client

from .config import get_settings


@lru_cache
def get_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)
