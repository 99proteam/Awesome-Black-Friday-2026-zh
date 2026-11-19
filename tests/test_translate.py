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


from datetime import datetime
from scripts.translate import assemble, disclaimer, render_readme, line_key as _k, TZ

DOC = "## 🔥 Productivity\n\n| -- | --- |\n|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |\n| <a href=\"https://a.com\"><img src=\"https://a.com/i.png\"></a> |\n"
ZH = {"## 🔥 Productivity": "## 🔥 生產力", "|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |": "|  ⭐ | [A](https://a.com) | 快速的 App。 | **BF26** |"}


def fake(calls, table=ZH):
    def tr(lines):
        calls.append(list(lines))
        return [table.get(l) for l in lines]
    return tr


def test_assemble_uses_cache_and_translates_misses():
    cache, calls = {}, []
    out1, _ = assemble(DOC, cache, fake(calls))
    assert "## 🔥 生產力" in out1 and "快速的 App。" in out1
    assert len(calls[0]) == 2
    calls2 = []
    out2, _ = assemble(DOC, cache, fake(calls2))
    assert out2 == out1
    assert all(c == [] for c in calls2)


def test_assemble_keeps_english_on_invalid():
    bad = dict(ZH)
    bad["|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |"] = "|  ⭐ | A | 快速的 App。 | **BF26** |"
    cache = {}
    out, _ = assemble(DOC, cache, fake([], bad))
    assert "| Fast app. |" in out
    assert cache[_k("|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |")] == "|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |"


def test_assemble_passthrough():
    out, _ = assemble(DOC, {}, fake([]))
    lines = out.split("\n")
    assert lines[1] == "" and lines[2] == "| -- | --- |"
    assert lines[4] == '| <a href="https://a.com"><img src="https://a.com/i.png"></a> |'
    assert out.endswith("\n")


T1 = datetime(2026, 11, 19, 23, 30, tzinfo=TZ)
T2 = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)


def test_render_readme_keeps_old_when_body_same():
    r1 = render_readme(None, "body\n", T1)
    assert render_readme(r1, "body\n", T2) == r1


def test_render_readme_bumps_time_on_change():
    r1 = render_readme(None, "body\n", T1)
    r2 = render_readme(r1, "body2\n", T2)
    assert "2026-11-20 08:00" in r2 and r2.endswith("body2\n")


def test_disclaimer_contents():
    d = disclaimer(T1)
    assert "https://github.com/trungdq88/Awesome-Black-Friday-Cyber-Monday" in d
    assert "claude-sonnet-5-5" in d and "（UTC+8）" in d and "2026-11-19 23:30" in d


import json
import os
from types import SimpleNamespace
import scripts.translate as tmod


class FakeClient:
    def __init__(self, bad_calls=()):
        self.calls = 0
        self.bad_calls = set(bad_calls)
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        batch = json.loads(kw["messages"][0]["content"])
        out = ["zh:" + l for l in batch]
        if self.calls in self.bad_calls:
            out = out[:-1]
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps({"translations": out}))],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


def test_translate_lines_batches():
    c = FakeClient()
    res = tmod.translate_lines(c, [f"l{i}" for i in range(85)], batch_size=40)
    assert c.calls == 3 and res == [f"zh:l{i}" for i in range(85)]


def test_translate_lines_keeps_english_on_bad_batch():
    c = FakeClient(bad_calls={2, 3})  # batch 2 fails, its retry fails too
    res = tmod.translate_lines(c, [f"l{i}" for i in range(85)], batch_size=40)
    assert res[40:80] == [None] * 40
    assert res[:40] == [f"zh:l{i}" for i in range(40)] and res[80:] == [f"zh:l{i}" for i in range(80, 85)]


def test_main_aborts_on_short_upstream(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("old", encoding="utf-8")
    monkeypatch.setattr(tmod, "fetch_upstream", lambda: "tiny")
    assert tmod.main() == 1
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "translations.json").exists()


# --- final review fixes ---
ROW = "|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |"


def test_validate_rejects_plain_code_change():
    s = "| Chat UI.<br/>BLACKFRIDAY2026<br/> |"
    assert not is_valid_translation(s, "| 聊天介面。<br/>BLACKFRIDAY2025<br/> |")


def test_validate_rejects_anchor_change():
    assert not is_valid_translation("- [Tools](#-tools)", "- [工具](#-工具)")


def test_validate_rejects_price_change():
    assert not is_valid_translation("| Lifetime ($190 → $95) |", "| 終身授權（$19 → $95） |")


def test_validate_rejects_backtick_change():
    assert not is_valid_translation("| Use `BF26` at checkout |", "| 結帳時使用 `BF25` |")


def test_assemble_saves_progress_before_crash():
    cache, n = {}, [0]
    def tr(lines):
        n[0] += 1
        if n[0] == 2:
            raise RuntimeError("boom")
        return [ZH.get(l) for l in lines]
    try:
        assemble(DOC, cache, tr, batch_size=1)
    except RuntimeError:
        pass
    assert _k("## 🔥 Productivity") in cache


def test_assemble_retries_invalid_once_then_caches_english():
    cache, calls = {}, []
    bad = {ROW: "|  ⭐ | A | 快 | **BF26** |"}
    out, failed = assemble(ROW + "\n", cache, fake(calls, bad))
    assert len(calls) == 2 and failed == 0
    assert cache[_k(ROW)] == ROW  # stop paying for it every run


def test_assemble_reports_api_failures():
    cache = {}
    out, failed = assemble(ROW + "\n", cache, lambda lines: [None] * len(lines))
    assert failed == 1 and _k(ROW) not in cache


def test_main_api_failure_exits_nonzero_keeps_readme(tmp_path, monkeypatch):
    big = Path("tests/fixtures/upstream.md").read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    (tmp_path / "README.md").write_text("old", encoding="utf-8")
    monkeypatch.setattr(tmod, "fetch_upstream", lambda: big)
    monkeypatch.setattr(tmod, "translate_lines", lambda client, lines: [None] * len(lines))
    assert tmod.main() == 1
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "translations.json").exists()
