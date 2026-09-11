
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings
from server.storage import create_s3_client, ensure_bucket_exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.s3_client = create_s3_client(settings)
    ensure_bucket_exists(app.state.s3_client, settings.s3_bucket_name)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
    )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.port,
        limit_concurrency=100,
        timeout_keep_alive=75,
        log_level="info",
    )
