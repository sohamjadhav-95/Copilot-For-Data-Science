"""
Session Manager — handles Playwright browser lifecycle and session persistence.
Supports multiple targets (GPT, Claude) each with their own storage state.
"""

import asyncio
from pathlib import Path

from loguru import logger
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

from config import settings
from core.selectors import URLS


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class SessionManager:
    """Manages one browser with per-target persistent contexts."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}  # target -> context
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_SESSIONS)
        self._initialized = False

    # ── Lifecycle ────────────────────────────────────────────

    async def initialize(self, headless: bool | None = None) -> None:
        if self._initialized:
            return

        hl = headless if headless is not None else settings.HEADLESS
        logger.info(f"Launching {settings.BROWSER_TYPE} (headless={hl})")

        self._playwright = await async_playwright().start()
        launcher = getattr(self._playwright, settings.BROWSER_TYPE)
        self._browser = await launcher.launch(
            headless=hl,
            slow_mo=settings.SLOW_MO,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        self._initialized = True
        logger.info("SessionManager initialized ✓")

    async def _get_or_create_context(self, target: str) -> BrowserContext:
        """Return a persistent context for the given target, creating it if needed."""
        if target in self._contexts:
            return self._contexts[target]

        storage_path = Path(settings.storage_state_path(target))
        context_opts: dict = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": _USER_AGENT,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "dark",
        }
        if storage_path.exists():
            logger.info(f"[{target}] Loading session from {storage_path}")
            context_opts["storage_state"] = str(storage_path)
        else:
            logger.warning(
                f"[{target}] No storage state — run /session/init?target={target} to log in."
            )

        ctx = await self._browser.new_context(**context_opts)

        if stealth_async:
            await stealth_async(ctx)

        ctx.set_default_timeout(settings.ELEMENT_TIMEOUT_MS)
        ctx.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT_MS)

        self._contexts[target] = ctx
        return ctx

    async def close(self) -> None:
        for ctx in self._contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        logger.info("SessionManager closed ✓")

    # ── Page Management ──────────────────────────────────────

    async def new_page(self, target: str = "gpt") -> Page:
        if not self._browser:
            raise RuntimeError("SessionManager not initialized.")
        ctx = await self._get_or_create_context(target)
        return await ctx.new_page()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    # ── Session Persistence ──────────────────────────────────

    async def save_session(self, target: str) -> str:
        ctx = self._contexts.get(target)
        if not ctx:
            raise RuntimeError(f"No active context for target '{target}'.")
        storage_path = Path(settings.storage_state_path(target))
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=str(storage_path))
        logger.info(f"[{target}] Session saved to {storage_path}")
        return str(storage_path)

    # ── Interactive Login ────────────────────────────────────

    async def interactive_login(self, target: str = "gpt") -> str:
        url = URLS.get(target, URLS["gpt"])
        logger.info(f"[{target}] Opening headed browser for login at {url}")

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False, slow_mo=50)
        storage_path = Path(settings.storage_state_path(target))
        context_opts: dict = {"viewport": {"width": 1280, "height": 900}, "user_agent": _USER_AGENT}
        if storage_path.exists():
            context_opts["storage_state"] = str(storage_path)

        context = await browser.new_context(**context_opts)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")

        logger.info(f"🔐  Log into {url}. Close the browser when done.")
        try:
            await page.wait_for_event("close", timeout=300_000)
        except Exception:
            pass

        storage_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(storage_path))
        logger.info(f"[{target}] Session saved → {storage_path}")

        await context.close()
        await browser.close()
        await pw.stop()

        # Reload context with new state
        if target in self._contexts:
            await self._contexts[target].close()
            del self._contexts[target]

        return str(storage_path)
