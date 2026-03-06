import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_ai_service
from core.config import get_settings, Settings
from providers.base import ProviderError
from schemas.chat import ChatRequest, ChatResponse
from services.ai_service import AIService

_ai_service_dep: Depends = Depends(get_ai_service)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest,
    service: AIService = _ai_service_dep,
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    try:
        return await asyncio.wait_for(
            service.chat(request), timeout=settings.request_timeout_seconds
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"AI service timed out after {settings.request_timeout_seconds}s",
        ) from None
    except ProviderError as exc:
        raw = str(exc)
        if "429" in raw or "RESOURCE_EXHAUSTED" in raw:
            detail = "rate limit exceeded"
        else:
            detail = raw
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from exc
