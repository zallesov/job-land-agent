#!/usr/bin/env python3
"""
Headed Playwright script that fills a job application form.

Usage:
  python3 apply_job_filler.py \\
    --apply-url "https://..." \\
    --fields /tmp/apply_fields_123.json \\
    --job-id 123 \\
    --report /tmp/apply_report_123.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright", file=sys.stderr)
    sys.exit(1)

# ── Field matching config ────────────────────────────────────────────────────

LABEL_MAP = {
    "first name":               "first_name",
    "given name":               "first_name",
    "last name":                "last_name",
    "surname":                  "last_name",
    "family name":              "last_name",
    "full name":                "full_name",
    "your name":                "full_name",
    "email":                    "email",
    "e-mail":                   "email",
    "phone":                    "phone",
    "mobile":                   "phone",
    "telephone":                "phone",
    "location":                 "location",
    "city":                     "location",
    "current location":         "location",
    "country":                  "country",
    "linkedin":                 "linkedin_url",
    "linkedin url":             "linkedin_url",
    "linkedin profile":         "linkedin_url",
    "website":                  "website_url",
    "personal website":         "website_url",
    "portfolio":                "website_url",
    "github":                   "github_url",
    "cover letter":             "cover_letter",
    "years of experience":      "years_of_experience",
    "years experience":         "years_of_experience",
    "salary":                   "salary_expectation",
    "compensation":             "salary_expectation",
    "expected salary":          "salary_expectation",
    "start date":               "start_date",
    "starting date":            "start_date",
    "earliest starting":        "earliest_starting_date",
    "available from":           "start_date",
    "when can you start":       "start_date",
    "how did you hear":         "how_did_you_hear",
    "how did you find":         "how_did_you_hear",
    "source":                   "how_did_you_hear",
    "excited about":            "enthusiasm_answer",
    "why do you want":          "enthusiasm_answer",
    "why are you interested":   "enthusiasm_answer",
    "what excites you":         "enthusiasm_answer",
    "most impressive":          "impressive_thing",
    "impressive thing":         "impressive_thing",
    "proudest achievement":     "impressive_thing",
    "work authorization":       "work_authorization_europe",
    "authorised to work":       "work_authorization_europe",
    "authorized to work":       "work_authorization_europe",
    "right to work":            "work_authorization_europe",
}

# Keys in fields JSON that are long-text answers — try fuzzy match against any label
FREETEXT_KEYS = {
    "cover_letter", "enthusiasm_answer", "impressive_thing",
    "assessment_notes", "work_experience_summary",
}

SKIP_KEYWORDS = [
    "gender", "race", "ethnicity", "disability", "veteran",
    "diversity", "pronouns", "lgbtq", "eeoc",
]

SUBMIT_KEYWORDS = [
    "submit", "apply now", "send application", "complete application",
]

CONSENT_KEYWORDS = ["gdpr", "consent", "privacy", "agree", "terms"]


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def match_label(label_text: str, fields: dict) -> str | None:
    n = normalize(label_text)
    # Exact LABEL_MAP match
    for kw, field_key in LABEL_MAP.items():
        if kw in n:
            return field_key
    # Fuzzy match: check if any field key's words appear in the label
    for key, val in fields.items():
        if not val or key in ("resume_path",):
            continue
        key_words = key.replace("_", " ").lower()
        if key_words in n or (len(key_words) > 8 and key_words[:8] in n):
            return key
    return None


def should_skip(label_text: str) -> bool:
    n = normalize(label_text)
    return any(kw in n for kw in SKIP_KEYWORDS)


def get_label_for_element(page: Page, element) -> str:
    try:
        aria = element.get_attribute("aria-label") or ""
        if aria:
            return aria
        ph = element.get_attribute("placeholder") or ""
        if ph:
            return ph
        el_id = element.get_attribute("id")
        if el_id:
            label = page.query_selector(f"label[for='{el_id}']")
            if label:
                return label.inner_text()
        label_text = element.evaluate("""el => {
            let p = el.parentElement;
            while (p) {
                if (p.tagName === 'LABEL') return p.innerText;
                const lbl = p.querySelector('label');
                if (lbl && lbl.innerText) return lbl.innerText;
                p = p.parentElement;
                if (p && (p.tagName === 'FORM' || p.tagName === 'BODY')) break;
            }
            return '';
        }""")
        return label_text or ""
    except Exception:
        return ""


def fill_field(page: Page, element, value: str, field_key: str, filled: list, errors: list):
    try:
        tag = element.evaluate("el => el.tagName.toLowerCase()")
        if tag == "input":
            input_type = (element.get_attribute("type") or "text").lower()
            if input_type in ("text", "email", "tel", "url", "number", "search", ""):
                element.fill("")
                element.type(value, delay=15)
                filled.append(field_key)
            elif input_type == "file":
                if value and Path(value).exists():
                    element.set_input_files(value)
                    filled.append(field_key)
                else:
                    errors.append(f"File not found: {value}")
        elif tag == "textarea":
            element.fill("")
            element.type(value, delay=5)
            filled.append(field_key)
        elif tag == "select":
            try:
                element.select_option(label=value)
                filled.append(field_key)
            except Exception:
                try:
                    element.select_option(value=value)
                    filled.append(field_key)
                except Exception as e:
                    errors.append(f"Could not select '{value}' for {field_key}: {e}")
    except Exception as e:
        errors.append(f"Error filling {field_key}: {e}")


def upload_resume(page: Page, resume_path: str, filled: list, errors: list):
    """Handle resume upload — tries hidden file input, then file-chooser via Attach button."""
    if not resume_path or not Path(resume_path).exists():
        errors.append(f"Resume not found: {resume_path}")
        return

    # Method 1: hidden <input type="file"> (most platforms)
    for file_input in page.query_selector_all("input[type='file']"):
        try:
            # Force-set even if hidden
            file_input.evaluate("(el, path) => { el.style.display = 'block'; }", resume_path)
            page.evaluate("""([selector, path]) => {
                const input = document.querySelector(selector);
                if (!input) return;
                const dt = new DataTransfer();
                fetch('file://' + path).catch(() => {});
            }""", ["input[type='file']", resume_path])
            file_input.set_input_files(resume_path)
            filled.append("resume")
            print(f"  Resume uploaded via hidden file input.", file=sys.stderr)
            return
        except Exception as e:
            pass  # Try next method

    # Method 2: Greenhouse "Attach" button → file chooser dialog
    attach_selectors = [
        "text=Attach",
        "button:has-text('Attach')",
        "a:has-text('Attach')",
        "[data-qa='resume-attach']",
        "label[for*='resume']",
        "label[for*='cv']",
    ]
    for sel in attach_selectors:
        try:
            btn = page.query_selector(sel)
            if not btn or not btn.is_visible():
                continue
            print(f"  Trying file chooser via '{sel}'...", file=sys.stderr)
            with page.expect_filechooser(timeout=5000) as fc_info:
                btn.click()
            fc = fc_info.value
            fc.set_files(resume_path)
            filled.append("resume")
            print(f"  Resume uploaded via file chooser.", file=sys.stderr)
            time.sleep(1)
            return
        except Exception as e:
            pass

    errors.append("Could not find a resume upload mechanism on this page.")


def handle_checkboxes(page: Page, fields: dict, filled: list, errors: list):
    """Handle GDPR consent and other required checkboxes."""
    for checkbox in page.query_selector_all("input[type='checkbox']"):
        try:
            if checkbox.is_checked():
                continue
            label = get_label_for_element(page, checkbox)
            n = normalize(label)
            if should_skip(n):
                continue
            if any(kw in n for kw in CONSENT_KEYWORDS):
                # Auto-check GDPR/consent checkboxes
                checkbox.check()
                filled.append(f"checkbox:{label[:40]}")
                print(f"  Checked consent: {label[:60]}", file=sys.stderr)
        except Exception:
            pass


def fill_form(page: Page, fields: dict) -> dict:
    filled = []
    unfilled = []
    errors = []

    # Step 1: Resume upload (special handling)
    upload_resume(page, fields.get("resume_path", ""), filled, errors)
    time.sleep(0.5)

    # Step 2: Text inputs and textareas
    for selector in [
        "input:not([type='hidden']):not([type='file']):not([type='submit'])"
        ":not([type='button']):not([type='checkbox']):not([type='radio'])",
        "textarea",
    ]:
        for element in page.query_selector_all(selector):
            try:
                if not element.is_visible():
                    continue
                label = get_label_for_element(page, element)
                if not label:
                    continue
                if should_skip(label):
                    continue

                field_key = match_label(label, fields)
                if field_key and field_key in fields:
                    value = fields[field_key]
                    if value:
                        print(f"  Filling '{label[:50]}' ({field_key}) ...", file=sys.stderr)
                        fill_field(page, element, str(value), field_key, filled, errors)
                    else:
                        unfilled.append(f"{field_key} (empty)")
                elif field_key:
                    unfilled.append(f"{field_key} (not in fields)")
                else:
                    unfilled.append(f"unknown: {label[:70]}")
            except Exception as e:
                errors.append(f"Error processing element: {e}")

    # Step 3: Select dropdowns
    for element in page.query_selector_all("select"):
        try:
            if not element.is_visible():
                continue
            label = get_label_for_element(page, element)
            if not label or should_skip(label):
                continue
            field_key = match_label(label, fields)
            if field_key and field_key in fields:
                value = fields[field_key]
                if value:
                    print(f"  Select '{label[:50]}' ({field_key}) → {value}...", file=sys.stderr)
                    fill_field(page, element, str(value), field_key, filled, errors)
                else:
                    unfilled.append(f"{field_key} (empty)")
            elif field_key:
                unfilled.append(f"{field_key} (not in fields)")
            else:
                unfilled.append(f"unknown select: {label[:60]}")
        except Exception:
            pass

    # Step 4: Consent checkboxes
    handle_checkboxes(page, fields, filled, errors)

    return {"filled_fields": filled, "unfilled_fields": unfilled, "errors": errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-url", required=True)
    parser.add_argument("--fields", required=True)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--timeout", type=int, default=30000)
    args = parser.parse_args()

    try:
        fields = json.loads(Path(args.fields).read_text())
    except Exception as e:
        print(f"ERROR: Could not read fields JSON: {e}", file=sys.stderr)
        sys.exit(1)

    screenshot_path = f"/tmp/apply_screenshot_{args.job_id}.png"

    print(f"Opening {args.apply_url} in Chrome (headed mode)...", file=sys.stderr)

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--start-maximized"],
            )
        except Exception:
            # Fallback to default Chromium if real Chrome not found
            browser = pw.chromium.launch(
                headless=False,
                args=["--start-maximized"],
            )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            accept_downloads=True,
        )
        page = context.new_page()

        try:
            page.goto(args.apply_url, timeout=args.timeout, wait_until="domcontentloaded")
            print("Page loaded.", file=sys.stderr)
        except PWTimeout:
            print("WARNING: Page load timed out, proceeding.", file=sys.stderr)
        except Exception as e:
            report = {"filled_fields": [], "unfilled_fields": [], "errors": [str(e)], "screenshot_path": ""}
            Path(args.report).write_text(json.dumps(report, indent=2))
            sys.exit(1)

        try:
            page.wait_for_selector("form, input, textarea", timeout=10000)
        except PWTimeout:
            print("WARNING: No form elements found.", file=sys.stderr)

        page.screenshot(path=f"/tmp/apply_before_{args.job_id}.png", full_page=False)

        print("Filling form fields...", file=sys.stderr)
        result = fill_form(page, fields)

        time.sleep(1)

        try:
            page.screenshot(path=screenshot_path, full_page=False)
        except Exception:
            screenshot_path = ""

        result["screenshot_path"] = screenshot_path

        print(f"\nFilled: {result['filled_fields']}", file=sys.stderr)
        print(f"Unfilled: {result['unfilled_fields']}", file=sys.stderr)
        if result["errors"]:
            print(f"Errors: {result['errors']}", file=sys.stderr)

        Path(args.report).write_text(json.dumps(result, indent=2))
        print(f"\nReport written to {args.report}", file=sys.stderr)
        print("Browser is open. DO NOT close this window until you have submitted.")
        print("Press Ctrl+C here or close Chrome when done.")

        try:
            while True:
                time.sleep(5)
                if not browser.is_connected():
                    break
        except KeyboardInterrupt:
            pass

        try:
            context.close()
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
