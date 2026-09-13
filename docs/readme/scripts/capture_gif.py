"""One-off script to build a demo GIF from the running demo instance.
Uses a fresh, stateless browser context (no cookies/history persisted) —
same isolation guarantee as an incognito window.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

BASE = "http://localhost:8001"
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR = OUT_DIR / "_gif_frames"
FRAMES_DIR.mkdir(exist_ok=True)

frames = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1100, "height": 620})
    page = context.new_page()

    def frame(name, wait=400):
        page.wait_for_timeout(wait)
        path = FRAMES_DIR / f"{name}.png"
        page.screenshot(path=str(path))
        frames.append(path)

    page.goto(f"{BASE}/?project=1", wait_until="networkidle")
    frame("01_list", 600)

    # Open the task edit popup for the 3rd row — checklist now lives inside it
    row = page.locator("table tbody tr").nth(2)
    row.locator("td").last.locator("button").click()
    frame("02_open", 500)

    # Add subtasks directly in the task popup
    add_form = page.locator(".checklist-add-form")
    add_form.locator('input[name="title"]').fill("Subtask one")
    frame("03_typed", 400)
    add_form.locator('button:has-text("Add")').click()
    frame("04_added", 500)

    add_form = page.locator(".checklist-add-form")
    add_form.locator('input[name="title"]').fill("Subtask two")
    add_form.locator('button:has-text("Add")').click()
    frame("05_added2", 500)

    # Check one off — progress updates live in the popup
    page.locator(".checklist-toggle").first.click()
    frame("06_checked", 600)

    # Close popup
    page.locator("text=Cancel").click()
    frame("07_closed", 500)

    browser.close()

# Assemble GIF
images = [Image.open(f).convert("P", palette=Image.ADAPTIVE) for f in frames]
durations = [900, 900, 700, 900, 900, 1200, 1200]
images[0].save(
    OUT_DIR / "checklist-demo.gif",
    save_all=True,
    append_images=images[1:],
    duration=durations,
    loop=0,
)
print("saved checklist-demo.gif")

for f in frames:
    f.unlink()
FRAMES_DIR.rmdir()
