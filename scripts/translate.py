"""Sync a zh-TW translation of the upstream Awesome Black Friday README, line by line."""
import hashlib
import re
import unicodedata
from collections import Counter

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
CODE_BOLD_RE = re.compile(r"\*\*([A-Z0-9][A-Z0-9_\-]*)\*\*")
TAG_RE = re.compile(r"<[^>]+>")


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
