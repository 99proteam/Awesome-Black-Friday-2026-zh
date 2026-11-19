# zh-TW translation sync — design

Date: 2026-11-19 · Status: approved by user

## Intent
Publish a Traditional Chinese (zh-TW) translation of
`trungdq88/Awesome-Black-Friday-Cyber-Monday` (`README.md`) in the public repo
`refinism-B/Awesome-Black-Friday-2026-zh`, kept in sync automatically as upstream changes
(upstream had 100+ commits in 24h on 2026-11-19).

## Goals
- Same content and format as upstream; translation only, no additions/removals/edits.
- Incremental: only new or changed lines are sent for translation.
- Fully automated, minimal moving parts.
- Header disclaimer (zh-TW) at top of README:
  1. This is only a Chinese translation for reading aid; link to upstream repo.
  2. Translated by Claude (model name + ID); read with the original; original prevails on conflict.
  3. Last updated date/time of the Chinese version.

## Non-goals / anti-goals
- No editorial changes, re-ordering, summarizing, or added commentary beyond the disclaimer.
- No Dockerfile / external infra. No local machine dependency.
- Anti-goal: a broken line (lost URL, lost discount code, broken table) is worse than an untranslated line.

## Constraints
- Upstream has no LICENSE. User accepted the risk and will contact the author separately.
- Runs on GitHub Actions; Anthropic API key in repo secret `ANTHROPIC_API_KEY` (set by user).
- Model: `claude-sonnet-5-5` for everything (user decision; Haiku considered and rejected:
  savings ~US$2–3/season vs. style/terminology inconsistency). User sets a spend limit in Console.

## Approaches considered
- **A. GitHub Actions cron + Claude API (chosen)** — cloud, deterministic, exact model label; pay per use.
- B. Claude Code cloud routine (`/schedule`) — uses subscription, but agent free-form editing makes
  "translation only" hard to guarantee.
- C. Local Windows scheduler + `claude -p` — stops when PC is off.

## Design
Files:
```
.github/workflows/sync.yml   cron every 30 min + workflow_dispatch; concurrency group (no overlap)
scripts/translate.py         fetch upstream → line-level cache lookup → translate misses → write README.md
translations.json            cache: sha256(English line) → zh-TW line
README.md                    disclaimer + translated content
tests/                       unit tests for pure logic
```

Flow per run:
1. Fetch upstream `README.md` (raw).
2. Split into lines. Pass through unchanged: blank lines, table separator rows (`| -- |`), lines
   with no translatable text (only images/HTML/URLs/emoji). Other lines: cache hit → reuse.
3. Cache misses batched to Claude (`effort: low`). Prompt rules: zh-TW (Taiwan usage); keep product
   names, URLs, discount codes, prices, emoji, markdown/HTML structure untouched; dates to Chinese
   format (e.g. `Nov 27 - Dec 1` → `11/27 – 12/1`). Response: same number of lines, as JSON.
4. Validate each translated line against its source: same URLs, same `**bold**` codes, same `|`
   count, same emoji. Fail → retry once → still fail: keep English line, log warning (not cached).
5. Headings: compute GitHub anchor slug for original and translated heading; rewrite in-doc
   `(#anchor)` links (TOC) to the new anchors.
6. Prepend disclaimer. If translated body unchanged vs current README → no commit. Else update
   timestamp (Asia/Taipei) and commit + push.

## Left to the builder
- Batch size, JSON response shape, retry/backoff details, slug implementation details,
  exact "no translatable text" heuristic, commit message wording.
- Cost logging: print `usage` totals per run in Actions log.
