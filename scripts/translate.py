"""Sync a zh-TW translation of the upstream Awesome Black Friday README, line by line."""
import hashlib
import json
import sys
import urllib.request
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import anthropic

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
CODE_BOLD_RE = re.compile(r"\*\*([A-Z0-9][A-Z0-9_\-]*)\*\*")
TAG_RE = re.compile(r"<[^>]+>")
CODE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(?=[A-Z0-9_-]*\d)(?=[A-Z0-9_-]*[A-Z])[A-Z0-9][A-Z0-9_-]{2,}(?![A-Za-z0-9])")
ANCHOR_RE = re.compile(r"\]\((#[^)]*)\)")
BACKTICK_RE = re.compile(r"`[^`]+`")
MONEY_RE = re.compile(r"[$€£¥]\s?\d[\d.,]*|\d+(?:\.\d+)?%")


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or ch == "⭐"


def needs_translation(line: str) -> bool:
    s = TAG_RE.sub("", line)
    s = re.sub(r"\]\([^)]*\)", "]", s)  # drop link targets, keep link text
    s = URL_RE.sub("", s)
    return bool(re.search(r"[A-Za-z]", s))


def line_key(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _invariants(line: str):
    return (
        Counter(URL_RE.findall(line)),
        Counter(CODE_BOLD_RE.findall(line)),
        Counter(TAG_RE.findall(line)),
        Counter(CODE_TOKEN_RE.findall(line)),
        Counter(ANCHOR_RE.findall(line)),
        Counter(BACKTICK_RE.findall(line)),
        Counter(MONEY_RE.findall(line)),
        line.count("|"),
        Counter(ch for ch in line if _is_emoji(ch)),
    )


def is_valid_translation(src: str, dst: str) -> bool:
    return _invariants(src) == _invariants(dst)


HEADING_RE = re.compile(r"^#{1,6} (.*)$")


def _slug(text: str) -> str:
    text = text.lower()
    kept = "".join(
        ch for ch in text
        if ch in " -‍" or unicodedata.category(ch)[0] in "LMN" or unicodedata.category(ch) == "Pc"
    )
    return kept.replace(" ", "-")


def heading_slugs(lines: list[str]) -> list[str | None]:
    seen: Counter = Counter()
    out: list[str | None] = []
    for line in lines:
        m = HEADING_RE.match(line)
        if not m:
            out.append(None)
            continue
        base = _slug(m.group(1))
        out.append(f"{base}-{seen[base]}" if seen[base] else base)
        seen[base] += 1
    return out


def rewrite_anchors(en_lines: list[str], zh_lines: list[str]) -> list[str]:
    mapping = {e: z for e, z in zip(heading_slugs(en_lines), heading_slugs(zh_lines)) if e and z and e != z}
    if not mapping:
        return zh_lines
    pat = re.compile(r"\(#(" + "|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)) + r")\)")
    return [pat.sub(lambda m: f"(#{mapping[m.group(1)]})", line) for line in zh_lines]


MODEL_ID = "claude-sonnet-5-5"
MODEL_NAME = "Claude Sonnet 5.5"
UPSTREAM_REPO = "https://github.com/trungdq88/Awesome-Black-Friday-Cyber-Monday"
MARKER = "<!-- translation-body -->"
TZ = ZoneInfo("Asia/Taipei")


def assemble(upstream: str, cache: dict[str, str], translate_lines: Callable[[list[str]], list[str | None]],
             batch_size: int = 40) -> tuple[str, int]:
    """Returns (body, number of lines lost to API failures). Mutates `cache` batch by batch."""
    en = upstream.split("\n")
    todo = list(dict.fromkeys(l for l in en if needs_translation(l) and line_key(l) not in cache))
    api_failed = 0
    for i in range(0, len(todo), batch_size):
        chunk = todo[i:i + batch_size]
        invalid = []
        for src, dst in zip(chunk, translate_lines(chunk)):
            if dst is None:
                api_failed += 1
            elif is_valid_translation(src, dst):
                cache[line_key(src)] = dst
            else:
                invalid.append(src)
        if invalid:
            for src, dst in zip(invalid, translate_lines(invalid)):
                if dst is not None and is_valid_translation(src, dst):
                    cache[line_key(src)] = dst
                else:
                    # failed validation twice: keep English and stop paying for it every run
                    print(f"warning: keeping English after 2 invalid translations: {src[:80]}")
                    cache[line_key(src)] = src
    zh = [cache.get(line_key(l), l) if needs_translation(l) else l for l in en]
    return "\n".join(rewrite_anchors(en, zh)), api_failed


def disclaimer(now: datetime) -> str:
    return (
        "> [!NOTE]\n"
        f"> - 本清單為 [trungdq88/Awesome-Black-Friday-Cyber-Monday]({UPSTREAM_REPO}) 的中文翻譯，僅供輔助閱讀。\n"
        f"> - 翻譯由 {MODEL_NAME}（`{MODEL_ID}`）自動產生，建議搭配原版查看，如有歧異以原版為準。\n"
        f"> - 中文版最後更新：{now.astimezone(TZ):%Y-%m-%d %H:%M}（UTC+8）\n"
    )


def render_readme(old_readme: str | None, body: str, now: datetime) -> str:
    if old_readme and MARKER in old_readme and old_readme.split(MARKER + "\n\n", 1)[-1] == body:
        return old_readme
    return disclaimer(now) + "\n" + MARKER + "\n\n" + body


UPSTREAM_RAW = "https://raw.githubusercontent.com/trungdq88/Awesome-Black-Friday-Cyber-Monday/main/README.md"
CACHE_FILE = "translations.json"
README_FILE = "README.md"

SYSTEM_PROMPT = """You translate lines of a Markdown README (a list of Black Friday software deals) from English into Traditional Chinese as used in Taiwan (zh-TW).

Input: a JSON array of Markdown lines. Output: {"translations": [...]} with exactly one translated line per input line, same order, same count. Never merge, split, drop or add lines.

Rules:
- Translate only; do not add, remove, summarize or reword content.
- Use Taiwan vocabulary (軟體, 影片, 折扣碼, 應用程式), never Mainland terms (软件/軟件, 視頻, 優惠碼).
- Keep unchanged: product and company names, URLs, link targets, discount codes, prices and currency, emoji, HTML tags, Markdown syntax (|, **, [], (), #, -, >), leading/trailing whitespace, and the number of | characters.
- Keep numbers as written (e.g. 15,000+); keep percentage discounts like "60% OFF" as-is; do not convert them to 折.
- Dates: "Nov 27 - Dec 1" -> "11/27 – 12/1"; "Nov 20" -> "11/20".
- Use full-width Chinese punctuation in Chinese prose (，。：；！？（）), but keep Markdown/HTML syntax characters ASCII.
- If a line has nothing to translate, return it unchanged."""

SCHEMA = {
    "type": "object",
    "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
    "required": ["translations"],
    "additionalProperties": False,
}


def _translate_batch(client, batch: list[str], usage: list[int]) -> list[str] | None:
    try:
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
        )
    except anthropic.APIError as e:
        print(f"warning: API error: {type(e).__name__}")
        return None
    usage[0] += resp.usage.input_tokens
    usage[1] += resp.usage.output_tokens
    if resp.stop_reason != "end_turn":
        print(f"warning: stop_reason={resp.stop_reason}")
        return None
    try:
        out = json.loads(next(b.text for b in resp.content if b.type == "text"))["translations"]
    except (StopIteration, ValueError, KeyError, TypeError):
        return None
    return out if isinstance(out, list) and len(out) == len(batch) else None


def translate_lines(client, lines: list[str], batch_size: int = 40) -> list[str | None]:
    usage = [0, 0]
    result: list[str | None] = []
    for i in range(0, len(lines), batch_size):
        batch = lines[i:i + batch_size]
        out = _translate_batch(client, batch, usage) or _translate_batch(client, batch, usage)
        if out is None:
            print(f"warning: batch {i // batch_size + 1} failed twice; keeping English for {len(batch)} lines")
        result.extend(out or [None] * len(batch))
    print(f"translated {len(lines)} lines; usage: input={usage[0]} output={usage[1]} tokens")
    return result


def fetch_upstream() -> str:
    req = urllib.request.Request(UPSTREAM_RAW, headers={"User-Agent": "zh-translation-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> int:
    try:
        upstream = fetch_upstream()
    except OSError as e:
        print(f"error: fetch upstream failed: {e}")
        return 1
    if len(upstream) < 20_000 or "\n## " not in upstream:
        print(f"error: upstream looks truncated ({len(upstream)} chars); aborting")
        return 1
    cache_path, readme_path = Path(CACHE_FILE), Path(README_FILE)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    old = readme_path.read_text(encoding="utf-8") if readme_path.exists() else None
    client = anthropic.Anthropic(timeout=300)
    try:
        body, api_failed = assemble(upstream, cache, lambda lines: translate_lines(client, lines))
    finally:  # keep every paid translation, even if the run crashes or times out
        with open(cache_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, ensure_ascii=False, indent=0, sort_keys=True)
            f.write("\n")
    if api_failed:
        print(f"::error::{api_failed} lines failed at the API; README not updated (cache progress saved)")
        return 1
    new = render_readme(old, body, datetime.now(TZ))
    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    untranslated = sum(1 for l in upstream.split("\n") if needs_translation(l) and line_key(l) not in cache)
    print(f"{'changed' if new != old else 'unchanged'}; untranslated lines: {untranslated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
