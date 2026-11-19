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
