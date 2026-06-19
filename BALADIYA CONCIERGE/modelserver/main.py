from __future__ import annotations

import hashlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    artifact_path: str = "artifacts/classifier.joblib"
    artifact_sha256: str = ""        # must be set; empty = skip check (dev only)
    artifact_ar_path: str = "artifacts/classifier_ar.joblib"   # Arabic sub-model (§8.3)
    artifact_ar_sha256: str = ""     # optional — empty = skip hash check
    service_token: str = ""          # shared secret from Vault / env
    env: str = "development"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        import os
        if os.getenv("ENV") == "testing":
            return (init_settings, env_settings, file_secret_settings)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)


settings = Settings()

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.env != "production"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger(__name__)


class StartupError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from modelserver.classifier import ClassifierService

    artifact_path = Path(settings.artifact_path)
    if not artifact_path.exists():
        raise StartupError(f"Artifact not found: {artifact_path}")

    if settings.artifact_sha256:
        actual = _sha256_file(artifact_path)
        expected = settings.artifact_sha256
        if actual != expected:
            raise StartupError(
                f"Artifact SHA-256 mismatch: got {actual}, expected {expected}\n"
                "Update model_card.md or re-export the artifact."
            )
        logger.info("artifact.sha256_ok", sha256=actual)
    else:
        logger.warning("artifact.sha256_skip", note="set ARTIFACT_SHA256 in production")

    ar_artifact_path: Path | None = None
    ar_path = Path(settings.artifact_ar_path)
    if ar_path.exists():
        if settings.artifact_ar_sha256:
            actual_ar = _sha256_file(ar_path)
            if actual_ar != settings.artifact_ar_sha256:
                raise StartupError(
                    f"AR artifact SHA-256 mismatch: got {actual_ar}, expected {settings.artifact_ar_sha256}"
                )
            logger.info("artifact_ar.sha256_ok", sha256=actual_ar)
        else:
            logger.warning("artifact_ar.sha256_skip", note="set ARTIFACT_AR_SHA256 in production")
        ar_artifact_path = ar_path
        logger.info("artifact_ar.loaded", path=str(ar_path))
    else:
        logger.warning("artifact_ar.not_found", path=str(ar_path), note="Arabic text falls back to main pipeline")

    app.state.classifier = ClassifierService(artifact_path, ar_artifact_path)
    logger.info("modelserver.ready", artifact=str(artifact_path))
    yield
    logger.info("modelserver.shutdown")


app = FastAPI(title="Baladiya Model Server", version="0.1.0", lifespan=lifespan)


# ── Auth ───────────────────────────────────────────────────────────────────

def _verify_service_token(x_service_token: Annotated[str | None, Header()] = None) -> None:
    """Validate the shared service credential.

    Returns 401 if missing or wrong. All callers must supply the token —
    the modelserver is not an open endpoint.
    """
    if not settings.service_token:
        return  # token check disabled in dev (settings.service_token not set)
    if x_service_token != settings.service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Service-Token",
        )


# ── Schemas ────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponseSchema(BaseModel):
    intent: str
    category: str
    confidence: float
    lang: str
    variety: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["ops"])
async def healthz(request: Request) -> dict:
    return {"status": "ok", "artifact": settings.artifact_path}


@app.post(
    "/classify",
    response_model=ClassifyResponseSchema,
    dependencies=[Depends(_verify_service_token)],
)
async def classify(request: Request, body: ClassifyRequest) -> ClassifyResponseSchema:
    result = request.app.state.classifier.predict(body.text)
    return ClassifyResponseSchema(**result.to_dict())
