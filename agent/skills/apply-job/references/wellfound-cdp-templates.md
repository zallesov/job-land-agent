# WellFound CDP Command Templates

Low-level `Runtime.evaluate` payloads for WellFound application forms. These are the
**fallback** for React-controlled fields that ignore a plain `agent-browser fill`.
For navigation, reading, snapshots, simple fields, and screenshots, use the
**agent-browser** CLI first (see the `read-web-pages` skill).

## Prerequisites

- Visible Chrome running at `localhost:9222` (`bash agent/start-chrome.sh`)
- agent-browser reset to that browser: `agent-browser close --all` once, then drive it
  with `agent-browser --cdp 9222 <cmd>`. Without `--cdp 9222` it uses its own headless
  browser — wrong session, invisible, and DataDome-blocked.

## agent-browser first (most fields)

```bash
agent-browser --cdp 9222 open <wellfound job apply url>
agent-browser --cdp 9222 snapshot -i          # find the Apply button + form refs
agent-browser --cdp 9222 click @e<apply>
agent-browser --cdp 9222 fill  @e<field> "value"
```

Drop to the raw `Runtime.evaluate` templates below only when a React field does not
update via `fill` (custom value setter needed), or for a bulk one-shot fill.

## Raw CDP (React forms / bulk fill)

- Run via `agent-browser --cdp 9222 eval '<expression>'`, or `browser_cdp(method="Runtime.evaluate", ...)`.
- For `browser_cdp`, get the Target ID from `browser_cdp(method="Target.getTargets")` —
  find the tab with the WellFound job URL.

## Click Apply button

```
method: Runtime.evaluate
target_id: <wellfound_tab_id>
expression: (() => { const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Apply'); if(btn) { btn.click(); return 'clicked'; } return 'not found'; })()
```

## Extract modal form structure

```
method: Runtime.evaluate
target_id: <wellfound_tab_id>
expression: (() => { const d = document.querySelector('[role="dialog"]'); if(!d) return 'no dialog'; const labels = [...d.querySelectorAll('label')].map(l => l.textContent.trim()).filter(Boolean); const inputs = [...d.querySelectorAll('input, textarea, select')].map(el => ({ tag: el.tagName, type: el.type || el.tagName, name: el.name, placeholder: el.placeholder, id: el.id, required: el.required })); return JSON.stringify({labels, inputs}); })()
```

## Fill React-controlled text fields (universal)

⚠️ **PITFALL:** `window.HTMLInputElement.prototype` can be undefined in sandboxed frames or certain SPAs (WellFound's dialog). Use `el.constructor.prototype` instead — it infers the prototype from the element itself and works everywhere.

Universal setter that handles both INPUT and TEXTAREA:
```javascript
function setValue(el, val) {
  const nativeSetter = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value').set;
  nativeSetter.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
```

One-liner per-field:
```javascript
const ns = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value').set;
ns.call(el, 'your text');
el.dispatchEvent(new Event('input', {bubbles:true}));
el.dispatchEvent(new Event('change', {bubbles:true}));
```

## Fill all form fields in one CDP call

Template (adapt field names and values):
```javascript
(() => {
  const d = document.querySelector('[role="dialog"]');

  function setInput(el, val) {
    const ns = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value').set;
    ns.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function setTextarea(el, val) {
    const ns = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value').set;
    ns.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }

  // LinkedIn
  setInput(d.querySelector('input[name="customQuestionAnswers[253132][answer]"]'), 'https://linkedin.com/in/yourhandle');
  // GitHub
  setInput(d.querySelector('input[name="customQuestionAnswers[253133][answer]"]'), 'https://github.com/yourhandle');

  // Radios — query by full ID from extraction step
  d.querySelector('#form-input--modal-form-3543496--customQuestionAnswers\\[253134\\]\\[jobListingQuestionOptionId\\]--150524').click(); // Visa: No
  d.querySelector('#form-input--modal-form-3543496--customQuestionAnswers\\[253135\\]\\[jobListingQuestionOptionId\\]--150525').click(); // 4+ yrs: Yes

  // Essay textareas
  setTextarea(d.querySelector('textarea[name="customQuestionAnswers[253136][answer]"]'), 'Q5 answer here');
  setTextarea(d.querySelector('textarea[name="customQuestionAnswers[253137][answer]"]'), 'Q6 answer here');
  setTextarea(d.querySelector('textarea[name="customQuestionAnswers[253138][answer]"]'), 'Q7 answer here');
  setTextarea(d.querySelector('textarea[name="customQuestionAnswers[253139][answer]"]'), 'Q8 answer here');

  return 'all fields filled';
})()
```

## Verify with snapshot

After filling, use `browser_cdp(method="Runtime.evaluate", target_id="<target_id>", params={"expression": "document.body.innerText"})` to confirm all values appear. Do NOT use browser_type/browser_click — they route through the wrong browser session and refs will be stale.
