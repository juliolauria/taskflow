"""One-off script to capture README screenshots from the running demo instance.
Uses a fresh (incognito-equivalent) browser context each run — no cookies/state persisted.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8001"
OUT = Path(__file__).resolve().parent.parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    def shot(url, name, wait=600):
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(wait)
        page.screenshot(path=str(OUT / name))
        print("saved", name)

    shot(f"{BASE}/?project=all", "active-tasks.png")
    shot(f"{BASE}/kanban", "kanban.png")
    shot(f"{BASE}/views", "views.png")

    # Task detail modal — opened via the row's "..." menu, with checklist activities visible.
    # Taller viewport so the full one-column popup fits without internal scroll.
    page.set_viewport_size({"width": 1280, "height": 1150})
    page.goto(f"{BASE}/?project=1", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.locator("table tbody tr").first.locator("td").last.locator("button").click()
    page.wait_for_timeout(500)

    add_form = page.locator(".checklist-add-form")
    for item in ["Draft outline", "Get feedback", "Finalize"]:
        add_form.locator('input[name="title"]').fill(item)
        add_form.locator('button:has-text("Add")').click()
        page.wait_for_timeout(350)
        add_form = page.locator(".checklist-add-form")

    page.locator(".checklist-toggle").first.click()
    page.wait_for_timeout(400)

    page.screenshot(path=str(OUT / "task-modal.png"))
    print("saved task-modal.png")
    page.locator("text=Cancel").click()
    page.wait_for_timeout(300)
    page.set_viewport_size({"width": 1280, "height": 800})

    # Manage statuses modal — opened via the gear icon (HTMX swap), not a standalone page
    page.locator('button[title="Manage statuses"]').first.click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "manage-statuses.png"))
    print("saved manage-statuses.png")

    browser.close()
