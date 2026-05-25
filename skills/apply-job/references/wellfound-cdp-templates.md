# WellFound CDP Command Templates

Reusable `browser_cdp` payloads for WellFound application forms.

## Prerequisites

- Chrome running at `localhost:9222`
- Target ID from `browser_cdp(method="Target.getTargets")` — find the tab with the WellFound job URL

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

## Fill React-controlled text field

For INPUT elements:
```javascript
function setValue(el, val) {
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  nativeSetter.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
```

For TEXTAREA elements:
```javascript
function setValue(el, val) {
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  nativeSetter.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
```

## Fill all form fields in one CDP call

Template (adapt field names and values):
```javascript
(() => {
  const d = document.querySelector('[role="dialog"]');

  function setInput(el, val) {
    const ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    ns.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function setTextarea(el, val) {
    const ns = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    ns.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }

  // LinkedIn
  setInput(d.querySelector('input[name="customQuestionAnswers[253132][answer]"]'), 'https://linkedin.com/in/zallesov');
  // GitHub
  setInput(d.querySelector('input[name="customQuestionAnswers[253133][answer]"]'), 'https://github.com/zallesov');

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

After filling, use `browser_snapshot()` to visually confirm all values appear. Do NOT use browser_type/browser_click — they route through Browserbase and refs will be stale.
