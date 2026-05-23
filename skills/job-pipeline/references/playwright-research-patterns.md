# Playwright Research Patterns

Concrete script templates for company/job research via Playwright + terminal().

## 1. Load Telegram Channel, Find Job Post, Extract Links

```
Channel: https://t.me/s/dev_connectablejobs
Goal: Find a specific job post by company name and extract apply links
```

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 ..."})
        
        # Load and scroll to load older messages
        await page.goto("https://t.me/s/dev_connectablejobs")
        await page.wait_for_timeout(3000)
        for i in range(10):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
        
        # Find the message containing the company
        links = await page.evaluate("""() => {
            const messages = document.querySelectorAll('.tgme_widget_message_bubble');
            for (const msg of messages) {
                if (msg.textContent.toLowerCase().includes('akvelon')) {
                    const anchors = msg.querySelectorAll('a');
                    return Array.from(anchors).map(a => ({href: a.href, text: a.textContent.trim() || '(link)'}));
                }
            }
            return null;
        }""")
        for l in links or []:
            print(f"{l['text']}: {l['href']}")
        
        await browser.close()

asyncio.run(main())
```

## 2. Read a Job Listing Page

```
URL: https://akvelon-bdc.peopleforce.io/careers/v/207290-senior-lead-java-sde-gl
Goal: Extract full job description text
```

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 ..."})
        
        await page.goto("<job_listing_url>")
        await page.wait_for_timeout(3000)
        
        text = await page.evaluate("() => document.body.innerText")
        print(text)
        
        await browser.close()

asyncio.run(main())
```

## 3. Google Search for Company Research

```
Query: Akvelon company overview clients Google engineering services
```

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 ..."})
        
        await page.goto("https://www.google.com/search?q=<encoded_query>")
        await page.wait_for_timeout(2000)
        
        # Extract from .g (Google result container)
        results = await page.evaluate("""() => {
            const items = document.querySelectorAll('.g');
            return Array.from(items).slice(0, 5).map(el => ({
                title: el.querySelector('h3')?.textContent || '',
                snippet: el.textContent.substring(0, 300)
            }));
        }""")
        
        await browser.close()
```

**CAPTCHA note**: If Google returns a CAPTCHA page (check for `google.com/sorry/` in URL), switch to DuckDuckGo or bypass by targeting the specific URL directly (company website, PeopleForce listing, etc.) rather than going through search.
