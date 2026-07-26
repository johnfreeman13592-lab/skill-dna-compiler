import base64
import re

from skill_dna_compiler.ui import (
    build_guided_walkthrough_data_uri,
    build_guided_walkthrough_html,
)


def test_walkthrough_is_six_scene_self_contained_simulation():
    html = build_guided_walkthrough_html("en")

    for scene in (
        "Start · Use my notes",
        "Step 1 · Choose notes",
        "Step 2 · Check data",
        "Step 3 · Review draft",
        "Step 4 · Save twice",
        "Complete · Finish",
    ):
        assert scene in html
    assert "setInterval(nextScene, 5000)" in html
    assert 'id="previous"' in html
    assert 'id="next"' in html
    assert 'id="pause"' in html
    assert 'class="dots"' in html
    assert 'id="counter">1 / 6' in html
    assert "prefers-reduced-motion:reduce" in html
    assert "let index=0,timer=0,paused=false" in html
    assert "if(!paused)timer=setInterval(nextScene, 5000)" in html
    assert "reduceMotion" not in html
    assert ".slide.active .pointer,.slide.active .ripple{animation:none}" in html
    assert ".ripple{display:none}" in html
    assert 'class="pointer"' in html
    assert 'class="ripple"' in html
    assert "SIMULATION · SAMPLE DATA ONLY" in html
    assert "does not read notes" in html
    assert "C:\\\\My Notes" in html
    assert "C:\\\\My Skills\\\\safe-data-change\\\\SKILL.md" in html
    assert re.search(r"[A-Za-z]:\\\\Users\\\\[^\\\\]+(?:\\\\|$)", html, re.IGNORECASE) is None
    assert "https://" not in html
    assert "window.parent" not in html


def test_walkthrough_uses_japanese_copy_and_data_uri_is_decodable():
    html = build_guided_walkthrough_html("ja")

    assert "シミュレーション・サンプルデータのみ" in html
    assert "実際の流れを最後まで見る" in html
    assert "一時停止" in html
    assert "前へ" in html
    assert "次へ" in html
    assert "終了" in html

    uri = build_guided_walkthrough_data_uri("ja")
    prefix, encoded = uri.split(",", maxsplit=1)
    assert prefix == "data:text/html;base64"
    assert base64.b64decode(encoded).decode("utf-8") == html
