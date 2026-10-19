import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routes import case, chat, health
from .services.errors import ServiceError

logging.basicConfig(level=logging.INFO)

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


app.include_router(health.router)
app.include_router(case.router)
app.include_router(chat.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1",port=8000)
