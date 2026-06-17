---
name: candidate-referral-posts
description: Use when drafting recommender-written candidate recommendation posts for community job boards, Telegram channels, or similar referral-based hiring forums.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [jobs, referrals, recommendation, hiring, telegram, writing]
    related_skills: [referral-post]
---

# Candidate Referral Posts

## Overview

Use this skill when the user needs a recommendation post written from another person's perspective — a former colleague, founder, manager, or collaborator posting about the candidate on a community board or referral-driven channel. The class is broader than any one board: the core workflow is to establish what the recommender personally witnessed, match the destination board's format, and produce a concise high-trust endorsement that the recommender can actually stand behind.

## When to Use

- A colleague needs text to post about the candidate on Telegram or another community board.
- The user asks for a recommendation message "from X's perspective".
- The destination expects short, structured candidate blurbs rather than a cover letter.

Do not use for:
- Candidate-written outreach messages to recruiters.
- Standard resumes, bios, or LinkedIn summaries.
- Formal reference letters with legal/HR framing.

## Workflow

### 1. Establish recommender facts first

Before drafting, confirm:
- Recommender full name
- Recommender language fluency
- Shared companies / projects with the candidate
- Recommender's role or credibility line, if it will be named publicly

Do not guess these facts. The shared-work-history boundary controls what claims are legitimate.

### 2. Read candidate source materials

Use the CV and any standing user profile/config to extract role targets, location constraints, compensation, visa status, and relevant links.

### 3. Inspect the destination board format

Look at recent posts in the target channel or board before drafting. Match:
- Section order
- Bullet density
- Tone and language
- Link placement
- Whether personal quote blocks or hashtags are common

### 4. Restrict claims to witnessed experience

This is the core integrity rule: include only achievements, behaviors, and strengths the recommender plausibly observed firsthand.

Allowed:
- Shared-company achievements
- Technical depth the recommender saw directly
- Leadership or ownership the recommender worked alongside

Not allowed:
- CV achievements from unrelated companies
- Management claims the recommender did not witness
- Inflated generic labels with no concrete supporting evidence

### 5. Draft concrete strengths, not vague praise

Prefer skill statements tied to observed evidence:
- "Expert knowledge in <specific platform/service>"
- "Built <system> from scratch at <shared company>"
- "Led <team/process> while delivering <outcome>"

Avoid empty labels like "strong communicator" or "distributed systems" unless they are anchored to concrete examples.

### 6. Compose the board-ready post

Typical sections:
- Header / candidate tag
- Recommender attribution
- Key achievements from shared work
- Distinct strengths / superpowers
- What the candidate is looking for
- Links
- Optional short personal endorsement

Save a draft copy under `tmp/` before presenting it so revisions do not destroy prior wording.

## Destination-specific subsection: Telegram community boards

Telegram community boards commonly prefer:
- Short headers or hashtags
- Tight bullet lists
- Direct recommender attribution up top
- Links collected at the bottom
- Brief, personal language instead of formal prose

## Reference files

- `references/rfoundersjobs-format.md` — concrete format notes and examples for one board subclass

## Common Pitfalls

1. **Referencing companies the recommender never worked at.** This is the most common failure mode.
2. **Using only the recommender's first name.** Get the public-facing full name.
3. **Writing in the board's language when the recommender cannot read it.** Optimize for what the recommender can approve.
4. **Listing vague strengths without evidence.** Tie every major claim to shared work.
5. **Turning the post into narrative paragraphs.** Many boards prefer compact bullet structure.
6. **Missing location / visa / compensation constraints.** These often determine response quality.

## Verification Checklist

- [ ] Recommender full name confirmed
- [ ] Recommender language confirmed
- [ ] Every achievement came from shared work history
- [ ] Claims are concrete and evidence-backed
- [ ] Board format was checked before drafting
- [ ] Candidate preferences (role, location, comp, visa) were sourced from real materials
- [ ] Draft saved before final presentation
