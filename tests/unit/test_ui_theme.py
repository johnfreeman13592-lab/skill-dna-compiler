from skill_dna_compiler.ui.theme import (
    hero_html,
    safety_sidebar_html,
    theme_css,
    workflow_html,
)


def test_theme_is_self_contained_and_respects_reduced_motion():
    css = theme_css().casefold()

    assert "http://" not in css
    assert "https://" not in css
    assert "@import" not in css
    assert "url(" not in css
    assert "prefers-reduced-motion" in css
    assert "focus-visible" in css
    assert "@media (max-width: 520px)" in css
    assert '[class*="st-"]' not in css


def test_hero_escapes_release_label_and_hides_dna_decoration():
    rendered = hero_html('<script src="external"></script>')

    assert "<script" not in rendered
    assert "&lt;script" in rendered
    assert 'class="sdc-dna-visual" aria-hidden="true"' in rendered
    assert "Skill DNA" in rendered


def test_workflow_preserves_the_five_explicit_product_steps():
    rendered = workflow_html()

    assert rendered.count('class="sdc-step"') == 5
    for label in ("SELECT", "SEQUENCE", "REVIEW", "COMPILE", "EXPORT"):
        assert label in rendered


def test_sidebar_shows_credential_state_without_a_secret_value():
    configured = safety_sidebar_html("v0.1.0-beta.2", api_key_configured=True)
    missing = safety_sidebar_html("v0.1.0-beta.2", api_key_configured=False)
    japanese = safety_sidebar_html(
        "v0.1.0-beta.2",
        api_key_configured=True,
        language="ja",
    )
    chinese = safety_sidebar_html(
        "v0.1.0-beta.2",
        api_key_configured=True,
        language="zh-CN",
    )

    assert "Configured; value hidden" in configured
    assert "Not configured; value hidden" in missing
    assert "設定済み・値は非表示" in japanese
    assert "已配置；不显示密钥值" in chinese
    assert "sk-secret-value" not in configured
