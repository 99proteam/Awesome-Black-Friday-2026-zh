# zh-TW Translation Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub Actions job that keeps `README.md` a line-for-line zh-TW translation of upstream `trungdq88/Awesome-Black-Friday-Cyber-Monday/README.md`, translating only new/changed lines via Claude.

**Architecture:** One script `scripts/translate.py`: pure functions (line classification, validation, slugs, assembly) + a thin Claude call + `main()`. A JSON line cache makes runs incremental. A cron workflow runs it every 30 min and commits only when the translated body changed.

**Tech Stack:** Python 3.12 (Actions) / 3.13 (local), `anthropic==2.10.0`, `pytest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-19-zh-translation-sync-design.md`

## Global Constraints

- Upstream raw URL: `https://raw.githubusercontent.com/trungdq88/Awesome-Black-Friday-Cyber-Monday/main/README.md`
- Upstream repo link in disclaimer: `https://github.com/trungdq88/Awesome-Black-Friday-Cyber-Monday`
- Model: `MODEL_ID = "claude-sonnet-5-5"`, `MODEL_NAME = "Claude Sonnet 5.5"`; `output_config={"effort": "low", ...}`. No fallbacks param (a fallback would make the disclaimer's model label false).
- API key only from env `ANTHROPIC_API_KEY`; never printed.
- Timezone `Asia/Taipei`, timestamp format `YYYY-MM-DD HH:MM（UTC+8）`.
- zh-TW (Taiwan usage). Untouched: product names, URLs, discount codes, prices, emoji, markdown/HTML syntax, `NN% OFF` (do not convert to 折).
- Dates: `Nov 27 - Dec 1` → `11/27 – 12/1`.
- Body marker separating disclaimer from body: `<!-- translation-body -->`.
- Cache file `translations.json`: `{sha256_hex_of_english_line: zh_line}`, `ensure_ascii=False`, `indent=0`, sorted keys.

## Review Focus

1. Upstream fetch fails or returns truncated/empty text → README and cache must stay untouched, job exits non-zero. (Task 4 test `test_main_aborts_on_short_upstream`)
2. Sponsored table rows mixing `<a href><img>`, `<br/>` and prose → tags preserved exactly. (Task 1 test `test_validate_rejects_lost_html_tag`)
3. API error / refusal / wrong line count for a batch → those lines stay English, are not cached, other batches still land. (Task 4 test `test_translate_lines_keeps_english_on_bad_batch`)
4. Two headings with same text → GitHub `-1` suffix anchors map correctly. (Task 2 test `test_slugs_dedupe_suffix`)
5. Unchanged upstream → README byte-identical (timestamp NOT bumped), no commit. (Task 3 test `test_render_readme_keeps_old_when_body_same`)

---

### Task 1: Line classification, cache key, validation

**Files:**
- Create: `scripts/translate.py`, `tests/test_translate.py`, `requirements.txt` (`anthropic==2.10.0`, `pytest`), `.gitignore` (`__pycache__/`, `.pytest_cache/`), `pytest.ini` (`[pytest]` / `pythonpath = .`)
- Create: `tests/fixtures/upstream.md` (snapshot of upstream README, fetched with `gh api repos/trungdq88/Awesome-Black-Friday-Cyber-Monday/contents/README.md -H "Accept: application/vnd.github.raw"`)

**Interfaces:**
- Produces: `needs_translation(line: str) -> bool`, `line_key(line: str) -> str`, `is_valid_translation(src: str, dst: str) -> bool`

- [ ] **Step 1: Write failing tests**

```python
from scripts.translate import needs_translation, line_key, is_valid_translation

def test_needs_translation():
    assert not needs_translation("")
    assert not needs_translation("| -- | ---| ------ | ------ |")
    assert not needs_translation('| <a href="https://x.com"><img src="https://x.com/a.png"></a> |')
    assert needs_translation("## 🔥 Productivity")
    assert needs_translation("|  ⭐ | [DevUtils](https://devutils.com) | All-in-one toolbox. | 60% OFF with code **BF2026** |")

def test_line_key_stable():
    assert line_key("abc") == line_key("abc") != line_key("abd")

SRC = "|  ⭐ | [DevUtils](https://devutils.com) | All-in-one toolbox. | 60% OFF with code **BF2026** (Nov 2 - Dec 1) |"
def test_validate_ok():
    assert is_valid_translation(SRC, "|  ⭐ | [DevUtils](https://devutils.com) | 一站式工具箱。 | 使用折扣碼 **BF2026** 享 60% OFF（11/2 – 12/1） |")
def test_validate_rejects_lost_url():
    assert not is_valid_translation(SRC, "|  ⭐ | DevUtils | 一站式工具箱。 | 使用折扣碼 **BF2026** 享 60% OFF |")
def test_validate_rejects_changed_code():
    assert not is_valid_translation(SRC, "|  ⭐ | [DevUtils](https://devutils.com) | 一站式工具箱。 | 使用 **BF2025** 享 60% OFF |")
def test_validate_rejects_pipe_change():
    assert not is_valid_translation(SRC, "|  ⭐ | [DevUtils](https://devutils.com) | 一站式工具箱。 使用折扣碼 **BF2026** 享 60% OFF |")
def test_validate_rejects_lost_emoji():
    assert not is_valid_translation(SRC, "|  | [DevUtils](https://devutils.com) | 一站式工具箱。 | 使用折扣碼 **BF2026** 享 60% OFF |")
def test_validate_rejects_lost_html_tag():
    s = "| Chat UI.<br/>BLACKFRIDAY2026<br/><br/>Use your key. |"
    assert not is_valid_translation(s, "| 聊天介面。<br/>BLACKFRIDAY2026<br/>用你的金鑰。 |")
def test_validate_allows_translated_prose_bold():
    assert is_valid_translation("- ⭐ **High quality deals only**: we review.", "- ⭐ **只收高品質優惠**：我們會審核。")
```

- [ ] **Step 2: Run** `python -m pytest tests -q` → FAIL (import error).
- [ ] **Step 3: Implement in `scripts/translate.py`** (+ empty `scripts/__init__.py`)
  - `needs_translation`: strip HTML tags, markdown link/image URLs, URLs, emoji, `|`, `-`, `:`, whitespace; True if any ASCII letter remains.
  - `line_key`: sha256 hex of UTF-8 line.
  - `is_valid_translation`: equal multisets of: URLs (`https?://[^\s)\]>"']+`), code-like bold `\*\*([A-Z0-9][A-Z0-9_\-]*)\*\*`, HTML tags (`<[^>]+>`), `|` count, emoji chars (`ord >= 0x1F000` or `0x2600–0x27BF`, plus `⭐`). Bold prose may change.
- [ ] **Step 4: Run** `python -m pytest tests -q` → all PASS.
- [ ] **Step 5: Commit** `feat: line classification and translation validation`

### Task 2: GitHub heading slugs and anchor rewrite

**Files:** Modify `scripts/translate.py`, `tests/test_translate.py`

**Interfaces:**
- Produces: `heading_slugs(lines: list[str]) -> list[str | None]` (slug per line, None for non-headings, with GitHub duplicate suffix `-1`, `-2`), `rewrite_anchors(en_lines: list[str], zh_lines: list[str]) -> list[str]` (replaces `(#en_slug)` with `(#zh_slug)` in every zh line)

- [ ] **Step 1: Failing tests**

```python
from pathlib import Path
import re
from scripts.translate import heading_slugs, rewrite_anchors

UP = Path("tests/fixtures/upstream.md").read_text(encoding="utf-8").splitlines()

def test_slugs_match_upstream_toc():
    slugs = {s for s in heading_slugs(UP) if s}
    for a in re.findall(r"\]\(#([^)]+)\)", "\n".join(UP)):
        assert a in slugs, a

def test_slugs_dedupe_suffix():
    assert heading_slugs(["## Tools", "x", "## Tools"]) == ["tools", None, "tools-1"]

def test_rewrite_anchors():
    en = ["- [🔥 Productivity ](#-productivity)", "## 🔥 Productivity"]
    zh = ["- [🔥 生產力 ](#-productivity)", "## 🔥 生產力"]
    assert rewrite_anchors(en, zh)[0] == "- [🔥 生產力 ](#-生產力)"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Slug = heading text (after `#`s and one space), lowercased, keep chars whose `unicodedata.category` starts with `L`, `M`, `N`, or is `Pc`, plus space, `-`, and U+200D if `test_slugs_match_upstream_toc` needs it; spaces → `-`. Let the fixture test decide edge chars.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: github anchor slugs and toc rewrite`

### Task 3: Assembly, disclaimer, README render

**Files:** Modify `scripts/translate.py`, `tests/test_translate.py`

**Interfaces:**
- Consumes: Task 1, Task 2 functions.
- Produces:
  - `assemble(upstream: str, cache: dict[str, str], translate_lines: Callable[[list[str]], list[str | None]]) -> str` — returns translated body; calls `translate_lines` once with all uncached translatable lines (deduped, order preserved); a `None` result or one failing `is_valid_translation` keeps the English line and is not cached; valid results are written into `cache` (mutated). Applies `rewrite_anchors`. Preserves trailing newline.
  - `disclaimer(now: datetime) -> str`
  - `render_readme(old_readme: str | None, body: str, now: datetime) -> str` — if `old_readme` contains marker and its body equals `body`, return `old_readme` unchanged; else `disclaimer(now) + "\n" + MARKER + "\n\n" + body`.

Disclaimer copy (exact):
```markdown
> [!NOTE]
> - 本清單為 [trungdq88/Awesome-Black-Friday-Cyber-Monday](https://github.com/trungdq88/Awesome-Black-Friday-Cyber-Monday) 的中文翻譯，僅供輔助閱讀。
> - 翻譯由 Claude Sonnet 5.5（`claude-sonnet-5-5`）自動產生，建議搭配原版查看，如有歧異以原版為準。
> - 中文版最後更新：{YYYY-MM-DD HH:MM}（UTC+8）
```

- [ ] **Step 1: Failing tests**
  - `test_assemble_uses_cache_and_translates_misses`: fake translator records calls; second `assemble` on same input with filled cache → translator called with `[]` or not at all; output identical.
  - `test_assemble_keeps_english_on_invalid`: fake returns line with URL removed → output has English line, cache lacks its key.
  - `test_assemble_passthrough`: separator rows, blank lines, image-only rows byte-identical.
  - `test_render_readme_keeps_old_when_body_same`: `render_readme(r1, body, t2) == r1` where `r1 = render_readme(None, body, t1)`.
  - `test_render_readme_bumps_time_on_change`: different body → contains `t2` formatted `2026-11-20 08:00`.
  - `test_disclaimer_contents`: contains upstream URL, `claude-sonnet-5-5`, `（UTC+8）`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the three functions + constants `MODEL_ID`, `MODEL_NAME`, `MARKER`, `TZ = ZoneInfo("Asia/Taipei")`. (`tzdata` to requirements if `ZoneInfo` fails on Windows.)
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: assemble translated readme with disclaimer`

### Task 4: Claude call and main()

**Files:** Modify `scripts/translate.py`, `tests/test_translate.py`

**Interfaces:**
- Produces:
  - `translate_lines(client, lines: list[str], batch_size: int = 40) -> list[str | None]` — per batch: `client.messages.create(model=MODEL_ID, max_tokens=16000, system=SYSTEM_PROMPT, output_config={"effort": "low", "format": {"type": "json_schema", "schema": {"type":"object","properties":{"translations":{"type":"array","items":{"type":"string"}}},"required":["translations"],"additionalProperties":False}}}, messages=[{"role":"user","content": json.dumps(batch, ensure_ascii=False)}])`. Parse first text block. Wrong length, `stop_reason != "end_turn"`, or `anthropic.APIError` → retry batch once → else `[None]*len(batch)`. Accumulate and print `usage` input/output token totals.
  - `main() -> int` — fetch upstream (urllib, 30 s timeout); if fetch fails or `len(text) < 20_000` or no `## ` heading → print error, return 1, write nothing. Load `translations.json` (missing → `{}`), `assemble`, `render_readme` against existing `README.md`, write README + cache (UTF-8, `\n` newlines). Print `changed`/`unchanged`.
  - `SYSTEM_PROMPT`: rules from Global Constraints; input is a JSON array of markdown lines; return `{"translations": [...]}` same length/order, one line each, never merge/split lines, keep leading/trailing whitespace and `|` structure.
- [ ] **Step 1: Failing tests** with a fake client object (`.messages.create` returns `SimpleNamespace(content=[SimpleNamespace(type="text", text=...)], stop_reason="end_turn", usage=SimpleNamespace(input_tokens=1, output_tokens=1))`):
  - `test_translate_lines_batches`: 85 lines, batch 40 → 3 calls, 85 results.
  - `test_translate_lines_keeps_english_on_bad_batch`: fake returns wrong length twice for batch 2 → those slots `None`, others filled.
  - `test_main_aborts_on_short_upstream`: monkeypatch fetch to return `"tiny"`, tmp cwd with existing README → return 1, README unchanged.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests -q` → PASS.
- [ ] **Step 5: Commit** `feat: claude translation and main entrypoint`

### Task 5: Workflow and first live run

**Files:** Create `.github/workflows/sync.yml`

- [ ] **Step 1: Write workflow**: `on: schedule: - cron: '*/30 * * * *'` + `workflow_dispatch`; `permissions: contents: write`; `concurrency: {group: sync, cancel-in-progress: false}`; steps: `actions/checkout@v4`, `actions/setup-python@v5` (`3.12`, pip cache), `pip install -r requirements.txt`, `python -m pytest tests -q`, `python scripts/translate.py` with `env: ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`, then `git add README.md translations.json && git diff --cached --quiet || (git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" commit -m "chore: sync translation" && git pull --rebase && git push)`.
- [ ] **Step 2: Commit** `ci: scheduled translation sync`, push `main` (user approves push).
- [ ] **Step 3: User sets secret** `ANTHROPIC_API_KEY` in repo settings.
- [ ] **Step 4: Trigger** `gh workflow run sync.yml`, watch `gh run watch`. Expected: run green, a `chore: sync translation` commit, README starts with disclaimer, log shows token totals.
- [ ] **Step 5: Verify live** (fresh verifier): pull; every `(#…)` link in README matches a heading slug; table rows have same `|` count as upstream; no English lines left except ones logged as failed; second manual run → "unchanged", no new commit.
