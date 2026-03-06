"""
FastAPI Application — REST API entry point.
Supports multiple models: GPT (chat.openai.com) and Claude (claude.ai).
"""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.models import (
    ChatRequest, ChatResponse, ErrorResponse,
    HealthResponse, SessionResponse,
)
from config import settings
from core.browser_agent import BrowserAgent
from core.session_manager import SessionManager
from utils import Timer

session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Browser Automation Agent…")
    try:
        await session_manager.initialize()
    except Exception as e:
        logger.warning(f"SessionManager init warning: {e}")
    yield
    logger.info("Shutting down…")
    await session_manager.close()


app = FastAPI(
    title="Browser Automation Agent",
    description="Automates GPT and Claude via real browser control.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        headless=settings.HEADLESS,
        max_concurrent=settings.MAX_CONCURRENT_SESSIONS,
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}},
    tags=["Chat"],
)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a prompt to the target model and return the response.

    - **model**: `"gpt"` → chat.openai.com | `"claude"` → claude.ai
    """
    async with session_manager.semaphore:
        page = None
        try:
            with Timer() as timer:
                page = await session_manager.new_page(request.model)
                agent = BrowserAgent(page, target=request.model)
                response_text = await agent.send_message(request.prompt)

            return ChatResponse(
                prompt=request.prompt,
                response=response_text,
                model=request.model,
                duration_ms=timer.elapsed_ms,
            )
        except RuntimeError as e:
            logger.error(f"Automation error [{request.model}]: {e}")
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(error="automation_error", detail=str(e)).model_dump(),
            )
        except Exception as e:
            logger.exception(f"Unexpected error [{request.model}]: {e}")
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(error="internal_error", detail=str(e)).model_dump(),
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass


@app.post(
    "/session/init",
    response_model=SessionResponse,
    tags=["Session"],
)
async def init_session(
    target: Literal["gpt", "claude"] = "gpt"
) -> SessionResponse:
    """
    Open a headed browser for manual login.

    - **target**: `"gpt"` or `"claude"` — which site to log into.
    """
    try:
        path = await session_manager.interactive_login(target)
        return SessionResponse(
            message=f"[{target}] Session initialized and saved.",
            target=target,
            storage_state_path=path,
        )
    except Exception as e:
        logger.exception(f"Session init failed [{target}]: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="session_init_error", detail=str(e)).model_dump(),
        )
