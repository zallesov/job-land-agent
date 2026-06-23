"""Open Explee in headed Playwright — sign in and wait."""
from playwright.sync_api import sync_playwright
import time, os, json, sys

COOKIE_FILE = os.path.expanduser("~/.explee_cookies.json")
SIGNAL_FILE = "/tmp/explee_signed_in"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context()

    # Load cookies if available
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            context.add_cookies(json.load(f))

    page = context.new_page()
    page.goto("https://explee.com/search")
    print(f"OK: {page.title()}")
    sys.stdout.flush()

    # Save cookies every 5 seconds
    def save():
        with open(COOKIE_FILE, "w") as f:
            json.dump(context.cookies(), f)

    print("Sign in now, then touch /tmp/explee_signed_in")
    sys.stdout.flush()

    while not os.path.exists(SIGNAL_FILE):
        save()
        time.sleep(3)

    save()
    os.remove(SIGNAL_FILE)
    print("READY — signed in and cookies saved.")
    sys.stdout.flush()

    while True:
        time.sleep(10)
