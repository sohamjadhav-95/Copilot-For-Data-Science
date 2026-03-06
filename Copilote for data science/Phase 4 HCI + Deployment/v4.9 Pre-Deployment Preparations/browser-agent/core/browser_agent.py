"""
Browser Agent — automation engine, now target-aware (GPT / Claude).
"""

import asyncio

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from config import settings
from core.selectors import TARGETS, URLS, DEFAULT_TARGET
from utils import async_retry, human_delay


class BrowserAgent:
    """Drives a browser page to interact with a chat interface."""

    def __init__(self, page: Page, target: str = DEFAULT_TARGET) -> None:
        self.page = page
        self.target = target.lower()
        self.sel = TARGETS.get(self.target, TARGETS[DEFAULT_TARGET])

    # ── Public API ───────────────────────────────────────────

    @async_retry(
        attempts=settings.RETRY_ATTEMPTS,
        backoff_base=settings.RETRY_BACKOFF_BASE,
    )
    async def send_message(self, prompt: str) -> str:
        logger.info(f"[{self.target}] Sending message ({len(prompt)} chars)…")
        await self._navigate()
        await self._type_message(prompt)
        await self._submit()
        await self._wait_for_response()
        response = await self._extract_response()
        logger.info(f"[{self.target}] Response received ({len(response)} chars)")
        return response

    # ── Navigation ───────────────────────────────────────────

    async def _navigate(self) -> None:
        target_url = URLS[self.target]
        current = self.page.url

        if target_url.split("/")[2] in current:  # same domain
            logger.debug(f"[{self.target}] Already on target domain — skipping nav.")
            return

        logger.debug(f"[{self.target}] Navigating to {target_url}")
        await self.page.goto(target_url, wait_until="domcontentloaded",
                             timeout=settings.NAVIGATION_TIMEOUT_MS)
        await self.page.wait_for_load_state("networkidle", timeout=30_000)
        await human_delay(500, 1500)

    # ── Type Message ─────────────────────────────────────────

    async def _type_message(self, prompt: str) -> None:
        input_el = await self._find_element(self.sel.INPUT_FIELD, "input field")
        await input_el.click()
        await human_delay(100, 300)

        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        await human_delay(100, 200)

        tag = await input_el.evaluate("el => el.tagName.toLowerCase()")
        is_ce = await input_el.evaluate(
            "el => el.getAttribute('contenteditable') === 'true'"
        )

        if tag == "textarea":
            await input_el.fill(prompt)
        elif is_ce:
            if len(prompt) > 200:
                await self._paste_text(prompt)
            else:
                await input_el.type(prompt, delay=15)
        else:
            await input_el.fill(prompt)

        await human_delay(200, 500)
        logger.debug(f"[{self.target}] Message typed ✓")

    async def _paste_text(self, text: str) -> None:
        await self.page.evaluate("text => navigator.clipboard.writeText(text)", text)
        await self.page.keyboard.press("Control+V")
        await human_delay(200, 400)

    # ── Submit ───────────────────────────────────────────────

    async def _submit(self) -> None:
        try:
            send_btn = await self._find_element(self.sel.SEND_BUTTON, "send button", timeout=3000)
            is_disabled = await send_btn.evaluate(
                "el => el.disabled || el.getAttribute('aria-disabled') === 'true'"
            )
            if not is_disabled:
                await send_btn.click()
                logger.debug(f"[{self.target}] Clicked send ✓")
                return
        except Exception:
            pass

        logger.debug(f"[{self.target}] Pressing Enter as fallback.")
        await self.page.keyboard.press("Enter")
        await human_delay(300, 600)

    # ── Wait for Response ────────────────────────────────────

    async def _wait_for_response(self) -> None:
        logger.debug(f"[{self.target}] Waiting for response to start…")
        streaming_appeared = False

        for selector in self.sel.STREAMING_INDICATOR:
            try:
                await self.page.wait_for_selector(selector, state="visible", timeout=15_000)
                streaming_appeared = True
                logger.debug(f"[{self.target}] Streaming started ({selector})")
                break
            except PlaywrightTimeout:
                continue

        if streaming_appeared:
            for selector in self.sel.STREAMING_INDICATOR:
                try:
                    await self.page.wait_for_selector(
                        selector, state="hidden", timeout=settings.RESPONSE_TIMEOUT_MS
                    )
                    logger.debug(f"[{self.target}] Streaming complete ({selector} hidden)")
                    break
                except PlaywrightTimeout:
                    continue
        else:
            logger.debug(f"[{self.target}] No streaming indicator — using text stabilization.")
            await self._wait_for_text_stabilization()

        await human_delay(1000, 2000)

    async def _wait_for_text_stabilization(
        self, check_interval_ms: int = 1500, stable_count: int = 3
    ) -> None:
        previous_text, stable_checks, total_waited = "", 0, 0
        max_wait = settings.RESPONSE_TIMEOUT_MS

        while total_waited < max_wait:
            await asyncio.sleep(check_interval_ms / 1000)
            total_waited += check_interval_ms
            current_text = await self._get_last_message_text()

            if current_text and current_text == previous_text:
                stable_checks += 1
                if stable_checks >= stable_count:
                    return
            else:
                stable_checks = 0
                previous_text = current_text

        logger.warning(f"[{self.target}] Text stabilization timed out — proceeding.")

    # ── Extract Response ─────────────────────────────────────

    async def _extract_response(self) -> str:
        text = await self._get_last_message_text()
        if not text:
            raise RuntimeError(f"[{self.target}] No assistant message found after waiting.")
        return text.strip()

    async def _get_last_message_text(self) -> str:
        for selector in self.sel.ASSISTANT_MESSAGE:
            elements = await self.page.query_selector_all(selector)
            if elements:
                last = elements[-1]
                for text_sel in self.sel.RESPONSE_TEXT:
                    text_el = await last.query_selector(text_sel)
                    if text_el:
                        return await text_el.inner_text()
                return await last.inner_text()
        return ""

    # ── Helpers ──────────────────────────────────────────────

    async def _find_element(self, selectors: list[str], label: str, timeout: int | None = None):
        t = timeout or settings.ELEMENT_TIMEOUT_MS
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, state="visible", timeout=t)
                if el:
                    return el
            except PlaywrightTimeout:
                continue
        raise RuntimeError(f"Could not find {label} using: {selectors}")
