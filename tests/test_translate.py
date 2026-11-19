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
    out1 = assemble(DOC, cache, fake(calls))
    assert "## 🔥 生產力" in out1 and "快速的 App。" in out1
    assert len(calls[0]) == 2
    calls2 = []
    out2 = assemble(DOC, cache, fake(calls2))
    assert out2 == out1
    assert all(c == [] for c in calls2)


def test_assemble_keeps_english_on_invalid():
    bad = dict(ZH)
    bad["|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |"] = "|  ⭐ | A | 快速的 App。 | **BF26** |"
    cache = {}
    out = assemble(DOC, cache, fake([], bad))
    assert "| Fast app. |" in out
    assert _k("|  ⭐ | [A](https://a.com) | Fast app. | **BF26** |") not in cache


def test_assemble_passthrough():
    out = assemble(DOC, {}, fake([]))
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
