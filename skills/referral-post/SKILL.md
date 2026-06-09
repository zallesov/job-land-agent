---
name: referral-post
description: Draft a job board recommendation post from a recommender's perspective. For Telegram/community job boards (rfoundersjobs, etc.) where a former colleague posts your profile on your behalf.
---

# Referral Post

## Trigger

User says: "prepare a message/recommendation from [Name] for [Board]", "draft a post for [person] to post about me", "напиши сообщение от [имени] для [борды]", or similar — a colleague needs to post a candidate profile on a community job board.

## Pre-flight: Collect recommender facts

Before drafting anything, assemble:
1. **Recommender's full name** — don't guess. The user told me "Tobias" in this session but later corrected to "Tobias Schutka". Ask explicitly.
2. **Recommender's language** — the channel is Russian but the recommender may not be. Ask or infer: "Does [Name] speak Russian, or should I write in English?"
3. **Shared company list** — explicitly confirm which companies/roles they worked at together. This is the most common source of errors.

## Workflow

### 1. Read source materials

```bash
# Read CV
cat config/cv.md

# Read user config for location/salary/visa
python3 -c "import yaml, json; d=yaml.safe_load(open('config/user.yaml')); print(json.dumps(d, indent=2))"
```

### 2. Study channel examples

Browse the target channel to see recent posts. Match their format, tone, and structure.
Use `browser_navigate` to view individual posts on the Telegram web view (`t.me/<channel>/<post_id>`).
Look for consistent patterns: section ordering, bullet style, link placement, hashtags.

### 3. Identify shared working history

**This is the critical step.** Ask the user (or infer from context) which companies the recommender and candidate worked at together.

- ✅ **Include only** roles/projects where the recommender was present and can personally vouch for.
- 🚫 **Never include** companies from other parts of the candidate's CV that the recommender didn't witness.
- If the candidate held a leadership role at a shared company, the recommender CAN reference it (they saw it).

### 4. Draft superpowers from recommender perspective

Each superpower area must include SPECIFIC evidence the recommender observed:

```
✅ Good: "AI-first engineering — built LangGraph feedback systems and production embedding pipelines at [shared company]"
✅ Good: "Expert knowledge in Google Cloud Services — architected and deployed autoscaling GPU clusters at [shared company]"
🚫 Bad: "Distributed Systems" (too generic, no recommender-specific evidence)
🚫 Bad: "Technical Leadership" (unless recommender saw the candidate lead a team)
```

**Preferred superpower format:** Use "Expert knowledge in <specific platform/service>" rather than generic "Cloud Architecture" or "Distributed Systems". The user explicitly approved "Expert knowledge in Google Cloud Services" — this is the preferred phrasing pattern.

Format tech skills as specific platform expertise with evidence from shared work.

Format tech skills as specific platform expertise: "Expert knowledge in X", not generic "Cloud Architecture".

### 5. Compose the post

**Language:** Check the recommender's language from the Pre-flight step. If they don't speak Russian, write in English. The channel accepts English posts. If unsure, default to English (the recommender needs to read and approve the draft).

**Structure (from rfoundersjobs format):**

```
#candidate <target title(s)>

Recommended by <Name>[, <role> at <company>]:

Key achievements & experience:
• <bullet — concrete, measurable, specific to shared work>
• <bullet>
• <bullet>

Superpowers:
• <skill area> — <specific evidence from shared work>
• <skill area> — <specific evidence>

What he's looking for:
• Position: <target roles>
• Industry: <target industries>
• Location: <location, visa status>
• Compensation: <salary>

Links:
CV → <link>
LinkedIn → <url>
Website → <url>

---

<Optional endorsing paragraph — 1-3 sentences, personal, confident tone>
```

**Bullet style:**
- Concrete and measurable where possible
- Start with strong verbs (built, led, architected, engineered, designed)
- Keep to 1-2 lines each
- Focus on outcomes, not responsibilities

**Endorsing paragraph (optional):**
- Brief, personal, confident
- One concrete observation about working style
- Standard closer: "Happy to chat if you want more context on what [Name] is capable of."
- Offer to chat for more context

**Save to tmp/ before presenting:**
Save the draft to `tmp/<recommender-name>_message.md` for the user to review. This lets them iterate without losing previous versions.

### 6. Present to user

Show the full draft in chat. Ask if they want changes. Do NOT send it anywhere without user approval.

## Reference files

- `references/rfoundersjobs-format.md` — detailed format breakdown with real examples

## Common pitfalls

- 🚫 **Including companies the recommender didn't work at** — the most common mistake. Only reference shared roles.
- 🚫 **Claiming "Technical Leadership" or "Management"** unless the recommender saw the candidate in that role.
- 🚫 **Generic skill labels like "Distributed Systems" or "Cloud Architecture"** — prefer the "Expert knowledge in <specific platform>" format the user explicitly approved.
- 🚫 **Writing narrative paragraphs** in the achievements section — bullet points are the established format.
- 🚫 **Over-aggregating** — keep each achievement specific and scoped to what that recommender witnessed.
- 🚫 **Including the recommender's full title** if you're unsure — ask the user.
- 🚫 **Forgetting visa/residence nuances** — check user config for location and relocation preference. EU-based with no visa needed is key info.
- 🚫 **Writing in Russian when the recommender doesn't speak it** — always check the recommender's language first. If they don't speak Russian, write the whole post in English.
- 🚫 **Using just a first name** — make sure you have the recommender's full name (first + last). Don't settle for a partial name; ask explicitly.
- 🚫 **Including skills/experience from the candidate's CV that the recommender never witnessed** — restrict content strictly to shared work history. The recommender can't vouch for things they didn't see.

## Visual reference

The rfoundersjobs posts follow this visual layout:
- Hashtag `#кандидат` at top with role titles
- A recommender attribution line in Russian (`Рекомендует [Name], [role] в [Company]:`)
- Bullet points with inline company links
- A blockquote with the recommender's personal words
- Links at bottom: LinkedIn, contact, CV
- Channel tag `@rfoundersjobs` at the very end

## Verification

Before presenting to the user:
1. ✅ Every company referenced is one the recommender witnessed
2. ✅ Superpowers include specific evidence, not just labels
3. ✅ No generic "Distributed Systems" — replaced with specific platform names
4. ✅ Language matches the recommender's fluent language
5. ✅ Compensation, location, and visa info are sourced from user config
