"""One-off script to seed the demo instance with fully generic project/task names."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8001"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()

    page.goto(f"{BASE}/?project=all", wait_until="networkidle")
    page.wait_for_timeout(400)

    # Rename projects to generic names via the rename endpoint directly
    import urllib.request

    def rename_project(pid, name):
        data = f"name={name}".encode()
        req = urllib.request.Request(f"{BASE}/projects/{pid}/rename", data=data, method="POST")
        urllib.request.urlopen(req)

    rename_project(1, "Project One")
    rename_project(2, "Project Two")

    page.goto(f"{BASE}/?project=1", wait_until="networkidle")
    page.wait_for_timeout(400)

    def add_task(title):
        page.locator('input[placeholder="Add a task and hit Enter…"]').click()
        page.keyboard.type(title)
        page.locator('button:has-text("Add")').first.click()
        page.wait_for_timeout(400)

    for t in ["Sample task one", "Sample task two", "Sample task three", "Sample task four"]:
        add_task(t)

    page.goto(f"{BASE}/?project=2", wait_until="networkidle")
    page.wait_for_timeout(400)
    for t in ["Sample task five", "Sample task six"]:
        add_task(t)

    browser.close()
    print("seeded demo data")
