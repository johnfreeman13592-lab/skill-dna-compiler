from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_default_quick_start_is_english_and_sample_first() -> None:
    quick_start = _read("docs/beta-quick-start.md")
    english_readme = _read("README.md")
    preserved_chinese_readme = _read("README.zh-CN.md")

    assert quick_start.startswith("# Skill DNA Compiler Beta Quick Start")
    assert "docs/beta-quick-start.md" in english_readme
    assert "docs/beta-quick-start.md" in preserved_chinese_readme
    assert "## 2. Free Sample Vault flow" in quick_start
    assert "## 3. Optional OpenAI API key" in quick_start
    assert quick_start.index("## 2. Free Sample Vault flow") < quick_start.index(
        "## 3. Optional OpenAI API key"
    )


def test_japanese_readme_links_japanese_quick_start() -> None:
    japanese_readme = _read("README.ja.md")
    japanese_quick_start = _read("docs/beta-quick-start.ja.md")

    assert "docs/beta-quick-start.ja.md" in japanese_readme
    assert japanese_quick_start.startswith("# Skill DNA Compiler Beta クイックスタート")
    assert "## 2. 無料のSample Vault" in japanese_quick_start
    assert "## 3. 後で実抽出を行う場合のOpenAI APIキー" in japanese_quick_start
    assert japanese_quick_start.index("## 2. 無料のSample Vault") < japanese_quick_start.index(
        "## 3. 後で実抽出を行う場合のOpenAI APIキー"
    )


def test_packaged_root_readme_source_is_the_english_quick_start() -> None:
    build_script = _read("tools/build_windows_beta.ps1")

    assert (
        'Copy-Item -LiteralPath "docs\\beta-quick-start.md" `\n'
        '        -Destination (Join-Path $bundlePath "README.txt")'
    ) in build_script
    assert 'Copy-Item -LiteralPath "docs\\beta-quick-start.ja.md" -Destination $docsPath' in (
        build_script
    )


def test_public_readmes_use_current_beta_download() -> None:
    expected_version = "v0.1.0-beta.4"
    expected_asset = "skill-dna-compiler-0.1.0-beta.4-windows-x64.zip"

    for relative in ("README.md", "README.ja.md", "README.zh-CN.md"):
        readme = _read(relative)
        assert expected_version in readme
        assert expected_asset in readme
        assert "v0.1.0-beta.3" not in readme
        assert "skill-dna-compiler-0.1.0-beta.3-windows-x64.zip" not in readme
