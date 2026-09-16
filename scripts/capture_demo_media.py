"""Regenerate README screenshots and the header GIF from a running dashboard.

Prerequisites (not part of requirements.txt):
    python -m pip install playwright
    Microsoft Edge installed, or change CHANNEL to "chrome".

Start the API on :8000 and a production frontend on :3000, then run:
    python scripts/capture_demo_media.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "demos"
URL = "http://localhost:3000"
CHANNEL = "msedge"
frames: list[Path] = []


def shot(page: Page, name: str, *, scroll: int = 0) -> None:
    page.evaluate(f"window.scrollTo(0, {scroll})")
    page.wait_for_timeout(1200)  # let chart entry animations finish
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    frames.append(path)
    print("captured", path.name)


def run(page: Page, button: str, endpoint: str) -> None:
    with page.expect_response(lambda r: endpoint in r.url and r.request.method == "POST", timeout=180_000) as response:
        page.get_by_role("button", name=button).last.click()
    if response.value.status != 200:
        msg = f"{endpoint} returned {response.value.status}"
        raise RuntimeError(msg)


def tab(page: Page, name: str) -> None:
    page.get_by_role("button", name=name, exact=True).first.click()
    page.wait_for_timeout(500)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHANNEL, headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)
        page.goto(URL, wait_until="networkidle")

        page.locator("select").first.select_option(label="Donchian Breakout")
        page.get_by_label("Trailing stop %").fill("12")
        run(page, "Run Backtest", "/api/backtest")
        shot(page, "single_run")

        tab(page, "Grid Search")
        page.locator("select").first.select_option(label="Donchian Breakout")
        page.get_by_label("Entry Window Range").fill("10, 20, 40, 55")
        page.get_by_label("Exit Window Range").fill("5, 10, 20")
        run(page, "Run Grid Search", "/api/grid-search")
        shot(page, "grid_search", scroll=420)

        tab(page, "Walk-Forward")
        run(page, "Run Walk Forward", "/api/walk-forward")
        shot(page, "walk_forward")

        tab(page, "AI Builder")
        page.get_by_role("button", name="Grid search an RSI strategy on NVDA from 2019 to 2023").click()
        run(page, "Generate Draft", "/api/ai/strategy-draft")
        shot(page, "ai_builder", scroll=760)

        tab(page, "Research Copilot")
        page.get_by_role("button", name="Walk-forward MSFT from 2018 to 2024 using a MACD crossover").click()
        run(page, "Create research plan", "/api/ai/research-plan")
        shot(page, "research_copilot", scroll=780)
        browser.close()

    # Per-frame palettes keep the red and green metric colors intact.
    images = [Image.open(path).convert("RGB").resize((1200, 675), Image.LANCZOS) for path in frames]
    quantized = [image.quantize(colors=224, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for image in images]
    quantized[0].save(OUT / "DemoHeader.gif", save_all=True, append_images=quantized[1:], duration=2200, loop=0, optimize=True)
    print("captured DemoHeader.gif")


if __name__ == "__main__":
    main()
