import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from api.routes import router
from api.rate_limit import rate_limit_router

load_dotenv()


def _validate_env_vars() -> None:
    """Raise RuntimeError for any required environment variable that is absent."""
    required = ["ANTHROPIC_API_KEY"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them before starting the server."
        )

_fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s")
_file_handler = RotatingFileHandler(
    os.getenv("LOG_FILE", "homebidder.log"),  # read before settings is importable
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=3,
)
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.DEBUG, handlers=[_console_handler, _file_handler])


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_env_vars()
    await init_db()
    yield


app = FastAPI(title="HomeBidder API", version="0.1.0", lifespan=lifespan)

from config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(rate_limit_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
