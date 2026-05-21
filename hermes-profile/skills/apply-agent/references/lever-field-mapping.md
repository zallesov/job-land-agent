# Lever ATS Field Mapping Reference

Tested on: HighLevel's Lever apply page (May 2026).
Job: Staff Engineer Platform Engineering, jobs.lever.co/gohighlevel/af42dc00-d62d-40cb-8c4b-4a595a32dd2c

## Standard Fields

| Label | Selector | Type | Required | Profile Mapping |
|---|---|---|---|---|
| Full name | `[name="name"]` | text | yes | basics.name |
| Email | `[name="email"]` | email | yes | basics.email |
| Phone | `[name="phone"]` | tel | yes | basics.phone |
| Current location | `#location-input` | text + structured | yes | basics.location |
| Current company | `[name="org"]` | text | yes | current_employment.company |
| LinkedIn URL | `[name="urls[LinkedIn]"]` | text | yes | links.linkedin |
| Twitter URL | `[name="urls[Twitter]"]` | text | no | — |
| GitHub URL | `[name="urls[GitHub]"]` | text | no | links.github |
| Portfolio URL | `[name="urls[Portfolio]"]` | text | no | links.website |
| Other website | `[name="urls[Other]"]` | text | no | — |

## Custom Cards

Cards are rendered from hidden template JSON stored in `<input type="hidden" name="cards[UUID][baseTemplate]">`.

### Current Employment Information
Card UUID: `5fd76fff-d276-4961-8fa4-a09cd4df4a38`

| Question | Selector | Type | Required | Notes |
|---|---|---|---|---|
| Current Compensation | `[name="cards[UUID][field0]"]` | text | yes | Use "Confidential" or profile value |
| Notice Period | `[name="cards[UUID][field1]"]` | radio | yes | Options: "90 days or less", "60 days or less", "45 days or less", "30 days or less", "15 days or less", "Immediately available" |
| Current Designation | `[name="cards[UUID][field2]"]` | text | no | e.g. "Senior AI Engineer (Staff Equivalent)" |

### Work Authorization - India
Card UUID: `0e99562a-862e-44f7-a43e-4a572d21afc4`

| Question | Selector | Type | Required | Notes |
|---|---|---|---|---|
| Legally authorised to work in India? | `[name="cards[UUID][field0]"]` | radio | yes | Yes/No |
| Require sponsorship in India? | `[name="cards[UUID][field1]"]` | radio | yes | Yes/No |

### Platform Engineering & AI Experience
Card UUID: `f5844aae-3551-4bc0-a8ed-d3a92d6a9f8b`

| Question | Selector | Type | Required | Notes |
|---|---|---|---|---|
| One large-scale system/platform built | `[name="cards[UUID][field0]"]` | textarea | yes | Generate from profile |
| AI tools for SDLC productivity | `[name="cards[UUID][field1]"]` | textarea | yes | Generate from profile |

## Resume Upload

- Visible button: link with text "ATTACH RESUME/CV" wrapping a hidden `<input id="resume-upload-input" type="file" name="resume">`
- The file input is invisible (CSS hidden). The styled link opens the system file chooser.
- Can't be automated via `browser_click` — Hermes browser tool can't interact with native file dialogs.
- Use Playwright's `locator('#resume-upload-input').setInputFiles('/path/to/resume.pdf')` for automation.

## Pronouns

- Checkbox group with name `pronouns`
- Standard options: He/him, She/her, They/them, Xe/xem, Ze/hir, Ey/em, Hir/hir, Fae/faer, Hu/hu
- Plus "Use name only" and "Custom" (free text)
- Select by clicking the input: `document.querySelector('[name="pronouns"][value="He/him"]').click()`

## Location Field Quirk

Lever's location field (`#location-input`) has a hidden autocomplete that:
- Is wired to Google Places-like structured selection
- Clears any programmatic `value=` assignment
- Needs `dispatchEvent(new Event('input', {bubbles: true}))` after setting value
- Even then, the `.value` property may remain empty after blur
- The hidden `#selected-location` input stores the structured result
- **Fallback**: flag for manual intervention if value doesn't persist

## Submit Button

- `[data-qa="btn-submit"]` — a `<button>` element, not `<input type="submit">`
- Has `type="button"`, not `type="submit"` — form submits via JS click handler
- The actual submit is intercepted by hCaptcha: `#hcaptchaSubmitBtn` is the real submit trigger
- hCaptcha sitekey: `e33f87f8-88ec-4e1a-9a13-df9bbb1d8120`
- If hCaptcha is not solved, the form won't submit — the button click triggers the captcha challenge
