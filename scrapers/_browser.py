"""Shared Playwright helpers with anti-bot stealth measures.

The three target sites (Kayak, Booking.com, GetYourGuide) all run aggressive
bot detection. A vanilla Playwright Chromium fails the `navigator.webdriver`
check, has an empty `navigator.plugins`, and ships a "HeadlessChrome" UA — any
of which trip the WAF. This module centralises a single stealth pass used by
every scraper.
"""
from __future__ import annotations

import asyncio
import random
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page


_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
]


_STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {name: 'Chrome PDF Plugin'},
        {name: 'Chrome PDF Viewer'},
        {name: 'Native Client'},
    ],
});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
const origQuery = window.navigator.permissions && window.navigator.permissions.query;
if (origQuery) {
    window.navigator.permissions.query = (p) =>
        p.name === 'notifications'
            ? Promise.resolve({state: Notification.permission})
            : origQuery(p);
}
"""


BOT_SIGNALS = (
    "just a moment",
    "captcha",
    "access denied",
    "verify you are human",
    "ddos-guard",
    "are you a robot",
    "unusual traffic",
    "press and hold",
    "checking your browser",
    "enable javascript and cookies to continue",
)

# Hard cap on text we ship to the LLM — keeps the prompt fast and cheap.
MAX_TEXT_CHARS = 20_000


def looks_blocked(text: str) -> bool:
    """Heuristic: does this page look like an interstitial / bot wall?"""
    if not text or len(text) < 300:
        return True
    low = text[:4000].lower()
    return any(sig in low for sig in BOT_SIGNALS)


def trim(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    """Keep the middle of long pages, since headers/footers are noise."""
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    return f"{head}\n\n[…content truncated…]\n\n{tail}"


async def fetch_page_text(
    browser: Browser,
    url: str,
    *,
    wait_for_selector: Optional[str] = None,
    extra_wait: float = 3.5,
    scroll: bool = True,
    timeout_ms: int = 45_000,
) -> str:
    """Open `url` in a fresh stealth context, return the rendered <body> text.

    Always closes its context — callers don't have to worry about leaks.
    """
    context: BrowserContext = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport={"width": 1366, "height": 800},
        locale="en-US",
        timezone_id="Europe/Madrid",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="121", "Google Chrome";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Upgrade-Insecure-Requests": "1",
        },
    )
    await context.add_init_script(_STEALTH_INIT_JS)

    page: Page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=15_000)
            except Exception:
                pass  # carry on with whatever loaded

        try:
            await page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass

        await asyncio.sleep(extra_wait)

        if scroll:
            # Trigger lazy-loaded result cards.
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(0.8)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.8)

        return await page.inner_text("body")
    finally:
        await context.close()
