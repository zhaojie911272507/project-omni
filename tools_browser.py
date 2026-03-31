"""High-level browser tool — search the web and extract page content.

Uses Playwright to drive a real Chromium browser, bypassing simple
anti-scraping measures. Search engine: DuckDuckGo HTML (lightweight, no JS).

Install:  pip install playwright && playwright install chromium
"""

from __future__ import annotations

import urllib.parse

from agent import tool


@tool(
    name="browser_search_and_extract",
    description=(
        "Search the web with a real browser and extract main-text content "
        "from the top results. Bypasses simple anti-scraping. "
        "Returns concatenated text from up to `max_results` pages."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of result pages to visit (default 3)",
            },
        },
        "required": ["query"],
    },
)
async def browser_search_and_extract(query: str, max_results: int = 3) -> str:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return (
            "[error] Playwright not installed. "
            "Run: pip install playwright && playwright install chromium"
        )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        # ── Step 1: Search via DuckDuckGo HTML (no JS needed) ─────────────
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15_000)

        raw_links: list[str] = await page.eval_on_selector_all(
            ".result__a",
            """els => els.map(e => {
                const href = e.getAttribute('href');
                if (href && href.startsWith('http')) return href;
                // DDG sometimes wraps in redirect; extract uddg param
                const m = href && href.match(/uddg=([^&]+)/);
                return m ? decodeURIComponent(m[1]) : null;
            }).filter(Boolean)""",
        )

        urls = _dedupe(raw_links)[:max_results]
        if not urls:
            await browser.close()
            return f"No search results found for: {query}"

        # ── Step 2: Visit each URL and extract main text ──────────────────
        results: list[str] = []
        for i, url in enumerate(urls, 1):
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=12_000)
                if resp and resp.status >= 400:
                    results.append(f"--- [{i}] {url} ---\n[http {resp.status}]")
                    continue

                text: str = await page.evaluate(_EXTRACT_JS)
                results.append(f"--- [{i}] {url} ---\n{text.strip()}")
            except Exception as exc:  # noqa: BLE001
                results.append(f"--- [{i}] {url} ---\n[error] {exc}")

        await browser.close()
        return "\n\n".join(results)


def _dedupe(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


_EXTRACT_JS = """
() => {
    // Prefer semantic containers, fall back to body
    const selectors = ['article', 'main', '[role="main"]',
                       '.post-content', '.entry-content', '.content', '#content'];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim().length > 200) {
            return el.innerText.trim().slice(0, 4000);
        }
    }
    return document.body.innerText.trim().slice(0, 4000);
}
"""
