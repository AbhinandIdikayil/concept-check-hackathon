"""Supabase client.

The backend talks to Supabase with the secret key, which bypasses row level
security. It must never be shipped to the browser.
"""

from __future__ import annotations  # noqa: I001

import logging
from functools import lru_cache

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from .config import get_settings

logger = logging.getLogger(__name__)

# A read can be sent again safely, so a lost connection is worth one more try.
# A write cannot: sending it twice would write the row twice. This is the same
# rule the PostgREST client applies to the Cloudflare errors it retries.
_REPEATABLE_METHODS = frozenset({"GET", "HEAD"})

# The connection died, not the query. The request never reached the database.
# A drop shows up as different errors depending on the protocol: HTTP/2 raises
# `RemoteProtocolError: Server disconnected`, HTTP/1.1 on Windows raises
# `ReadError` with a connection reset.
_LOST_CONNECTION = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
)

# Long enough for a slow query, short enough that a dead connection does not
# hold a worker thread for two minutes.
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=5.0)


class _RetryingTransport(httpx.HTTPTransport):
    """Transport that re-sends a read whose connection died.

    httpx keeps connections in a pool and hands them back out. Supabase sits
    behind a proxy that closes idle connections, and the pooled connection
    httpx picks up is sometimes already dead. The request then fails with
    `RemoteProtocolError: Server disconnected`.

    Neither httpx nor PostgREST covers that case: httpx's own `retries` only
    covers failures to open a connection, and PostgREST only retries 503 and
    520 responses. The failed request never reached the database, so sending
    it again is safe.
    """

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method not in _REPEATABLE_METHODS:
            return super().handle_request(request)

        try:
            return super().handle_request(request)
        except _LOST_CONNECTION as exc:
            logger.warning("retrying after the connection dropped: %s", exc)
            return super().handle_request(request)


@lru_cache
def get_client() -> Client:
    settings = get_settings()
    http_client = httpx.Client(
        timeout=_TIMEOUT,
        transport=_RetryingTransport(http2=True),
        follow_redirects=True,
    )
    options = SyncClientOptions(httpx_client=http_client)
    return create_client(settings.supabase_url, settings.supabase_key, options)
