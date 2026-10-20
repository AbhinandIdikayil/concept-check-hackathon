import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from postgrest import APIError as PostgrestAPIError

from .config import get_settings
from .routes import case, chat, health
from .services.errors import ServiceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Concept Check API", version="1.0.0")
settings = get_settings()

origins = (
    ["*"]
    if settings.cors_origins.strip() == "*"
    else [
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(httpx.RequestError)
async def upstream_unavailable_handler(_: Request, exc: httpx.RequestError) -> JSONResponse:
    """Supabase could not be reached: the connection was refused or dropped.

    Without this the failure surfaces as an unhandled 500 and uvicorn prints
    the whole transport stack. The database is simply not available right now,
    which is a 503, and the client can say so.
    """
    logger.error("the database could not be reached: %s", exc, exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "the database is not reachable right now, please try again"},
    )


@app.exception_handler(PostgrestAPIError)
async def database_error_handler(_: Request, exc: PostgrestAPIError) -> JSONResponse:
    """Supabase answered, and the answer was an error."""
    logger.error("the database rejected the request: %s", exc, exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "the database could not complete the request, please try again"},
    )


app.include_router(health.router)
app.include_router(case.router)
app.include_router(chat.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1",port=8000)
