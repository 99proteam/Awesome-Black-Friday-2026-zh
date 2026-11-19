"""Sync a zh-TW translation of the upstream Awesome Black Friday README, line by line."""
import hashlib
import re
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
