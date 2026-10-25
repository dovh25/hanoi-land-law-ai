"""Anonymous, stateless demo API. No authentication, no database, no session storage."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from langchain_core.messages import AIMessage, HumanMessage

from backend.models.demo import DemoChatRequest, DemoChatResponse, DemoRateLimit
from backend.services.pipelines.mvp_rag_pipeline import MvpRagPipeline
from backend.services.rate_limit import DemoRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])


def _pipeline(request: Request) -> MvpRagPipeline:
    pipeline = getattr(request.app.state, "mvp_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MVP demo is not enabled",
        )
    if not pipeline.is_initialized:
        try:
            pipeline.startup()
        except FileNotFoundError:
            logger.error("MVP demo corpus artifact is missing")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MVP demo corpus is unavailable",
            ) from None
    return pipeline


def _limiter(request: Request) -> DemoRateLimiter:
    limiter = getattr(request.app.state, "demo_limiter", None)
    if limiter is None:
        settings = request.app.state.settings
        limiter = DemoRateLimiter(
            settings.MVP_RATE_LIMIT_PER_MINUTE, settings.MVP_RATE_LIMIT_PER_DAY
        )
        request.app.state.demo_limiter = limiter
    return limiter


def _history(payload: DemoChatRequest, settings):
    messages = payload.history[-settings.MVP_MAX_HISTORY_MESSAGES:] if settings.MVP_MAX_HISTORY_MESSAGES else []
    converted = []
    used = 0
    for item in messages:
        content = item.content.strip()
        if used + len(content) > settings.MVP_MAX_HISTORY_CHARS:
            break
        converted.append(HumanMessage(content=content) if item.role == "user" else AIMessage(content=content))
        used += len(content)
    return converted


@router.get("/demo/info")
def demo_info(request: Request):
    settings = request.app.state.settings
    pipeline = _pipeline(request)
    return pipeline.info(settings)


@router.post("/demo/chat", response_model=DemoChatResponse, status_code=status.HTTP_200_OK)
def demo_chat(payload: DemoChatRequest, request: Request) -> DemoChatResponse:
    settings = request.app.state.settings
    pipeline = _pipeline(request)

    if len(payload.message) > settings.MVP_MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Câu hỏi tối đa {settings.MVP_MAX_MESSAGE_CHARS} ký tự.",
        )

    client = request.client.host if request.client and request.client.host else "unknown"
    decision = _limiter(request).check(client)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã gửi quá nhiều câu hỏi. Vui lòng thử lại sau.",
            headers={"Retry-After": str(decision.retry_after)},
        )

    try:
        result = pipeline.respond(
            payload.message.strip(),
            history=_history(payload, settings),
        )
    except Exception:
        # Never log user questions or provider details.
        logger.exception("MVP demo request failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xử lý yêu cầu. Vui lòng thử lại.",
        ) from None

    result["request_id"] = uuid.uuid4().hex
    result["rate_limit"] = DemoRateLimit(
        limit=decision.limit, remaining=decision.remaining
    ).model_dump()
    return DemoChatResponse(**result)
