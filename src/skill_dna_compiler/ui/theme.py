from __future__ import annotations

from html import escape

import streamlit as st

from .i18n import Language, text


def theme_css() -> str:
    """Return the self-contained visual theme without external assets."""

    return """
<style>
:root {
  --dna-bg: #050816;
  --dna-surface: rgba(13, 20, 44, 0.78);
  --dna-surface-strong: rgba(18, 28, 58, 0.94);
  --dna-line: rgba(132, 156, 255, 0.22);
  --dna-text: #f4f7ff;
  --dna-muted: #aab5d6;
  --dna-cyan: #43e7ff;
  --dna-violet: #8d72ff;
  --dna-magenta: #ff63d8;
  --dna-green: #62f6bd;
  --dna-warning: #ffd37a;
  --dna-radius: 20px;
  --dna-shadow: 0 24px 70px rgba(0, 0, 0, 0.34);
}

[data-testid="stAppViewContainer"] {
  color: var(--dna-text);
  background:
    radial-gradient(circle at 8% 8%, rgba(67, 231, 255, 0.13), transparent 28rem),
    radial-gradient(circle at 92% 12%, rgba(255, 99, 216, 0.12), transparent 30rem),
    radial-gradient(circle at 55% 80%, rgba(141, 114, 255, 0.12), transparent 34rem),
    linear-gradient(145deg, #040711 0%, #080d20 48%, #07091a 100%);
}

[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: 0.2;
  background-image:
    linear-gradient(rgba(120, 149, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120, 149, 255, 0.08) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(to bottom, black, transparent 82%);
}

[data-testid="stHeader"] { background: transparent; }

.stMainBlockContainer {
  max-width: 1500px;
  padding-top: 2rem;
  padding-bottom: 5rem;
}

html, body, [data-testid="stAppViewContainer"] {
  font-family: Inter, "Segoe UI Variable", "Yu Gothic UI", "Noto Sans JP", sans-serif;
}

h1, h2, h3 {
  color: var(--dna-text) !important;
  letter-spacing: -0.025em;
}

p, li, label, [data-testid="stCaptionContainer"] { color: #dce3fa; }
[data-testid="stCaptionContainer"] { color: var(--dna-muted); }

.sdc-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.55fr);
  gap: 2rem;
  align-items: center;
  min-height: 330px;
  margin-bottom: 1.35rem;
  padding: clamp(1.5rem, 4vw, 3.5rem);
  border: 1px solid rgba(122, 151, 255, 0.3);
  border-radius: 30px;
  background:
    linear-gradient(135deg, rgba(16, 27, 61, 0.96), rgba(11, 15, 38, 0.88)),
    linear-gradient(90deg, rgba(67, 231, 255, 0.1), rgba(255, 99, 216, 0.1));
  box-shadow: var(--dna-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.sdc-hero::after {
  content: "";
  position: absolute;
  width: 420px;
  height: 420px;
  right: -140px;
  top: -210px;
  border-radius: 50%;
  background: rgba(141, 114, 255, 0.22);
  filter: blur(70px);
}

.sdc-kicker {
  display: inline-flex;
  gap: 0.55rem;
  align-items: center;
  margin-bottom: 1rem;
  color: var(--dna-cyan);
  font-size: 0.78rem;
  font-weight: 750;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.sdc-kicker::before {
  content: "";
  width: 34px;
  height: 1px;
  background: linear-gradient(90deg, var(--dna-cyan), var(--dna-magenta));
}

.sdc-hero h1 {
  max-width: 850px;
  margin: 0;
  font-size: clamp(2.55rem, 6vw, 5.45rem);
  line-height: 0.96;
  font-weight: 800;
  background: linear-gradient(100deg, #ffffff 5%, #aeefff 48%, #ddc9ff 78%, #ffb9ed);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent !important;
}

.sdc-hero-copy {
  max-width: 780px;
  margin: 1.25rem 0 1.3rem;
  color: #cbd5f3;
  font-size: clamp(1rem, 1.6vw, 1.16rem);
  line-height: 1.75;
}

.sdc-pill-row { display: flex; flex-wrap: wrap; gap: 0.65rem; }
.sdc-pill {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0.38rem 0.8rem;
  border: 1px solid rgba(132, 156, 255, 0.28);
  border-radius: 999px;
  background: rgba(8, 13, 32, 0.58);
  color: #dce5ff;
  font-size: 0.78rem;
  font-weight: 650;
}

.sdc-dna-visual {
  position: relative;
  z-index: 1;
  width: min(290px, 100%);
  min-height: 250px;
  margin-inline: auto;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(67, 231, 255, 0.1), transparent 66%);
}

.sdc-strand {
  position: absolute;
  inset: 18px 34%;
  border-left: 3px solid var(--dna-cyan);
  border-right: 3px solid var(--dna-magenta);
  border-radius: 50%;
  transform: rotate(18deg);
  filter: drop-shadow(0 0 13px rgba(67, 231, 255, 0.5));
  animation: dna-float 7s ease-in-out infinite;
}

.sdc-rung {
  position: absolute;
  left: 25%;
  width: 50%;
  height: 2px;
  top: var(--rung-top);
  transform: rotate(var(--rung-angle));
  background: linear-gradient(90deg, var(--dna-cyan), var(--dna-violet), var(--dna-magenta));
  box-shadow: 0 0 15px rgba(141, 114, 255, 0.5);
}

.sdc-rung::before, .sdc-rung::after {
  content: "";
  position: absolute;
  top: -4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #e7faff;
  box-shadow: 0 0 13px var(--dna-cyan);
}
.sdc-rung::before { left: -3px; }
.sdc-rung::after { right: -3px; box-shadow: 0 0 13px var(--dna-magenta); }

.sdc-workflow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.7rem;
  margin: 0 0 1.5rem;
}

.sdc-step {
  position: relative;
  min-height: 104px;
  padding: 1rem;
  border: 1px solid var(--dna-line);
  border-radius: 17px;
  background: linear-gradient(145deg, rgba(18, 28, 58, 0.82), rgba(8, 13, 32, 0.76));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.sdc-step-number {
  display: inline-grid;
  place-items: center;
  width: 29px;
  height: 29px;
  margin-bottom: 0.65rem;
  border: 1px solid rgba(67, 231, 255, 0.45);
  border-radius: 50%;
  color: var(--dna-cyan);
  font-size: 0.72rem;
  font-weight: 800;
}
.sdc-step strong { display: block; color: #f4f7ff; font-size: 0.88rem; }
.sdc-step span:last-child { color: var(--dna-muted); font-size: 0.72rem; }

[data-testid="stSidebar"] {
  border-right: 1px solid rgba(132, 156, 255, 0.19);
  background: linear-gradient(180deg, rgba(7, 12, 29, 0.98), rgba(10, 15, 34, 0.98));
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #dce3fa; }
.sdc-side-title { margin: 0 0 0.9rem; color: #fff; font-weight: 760; }
.sdc-safety-card {
  margin-bottom: 0.65rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid rgba(98, 246, 189, 0.2);
  border-radius: 13px;
  background: rgba(13, 36, 40, 0.42);
}
.sdc-safety-card strong { display: block; color: var(--dna-green); font-size: 0.8rem; }
.sdc-safety-card span { color: #b9c7e4; font-size: 0.72rem; }
.sdc-build {
  margin-top: 1rem;
  color: #7f8caf;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 0.7rem;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: var(--dna-line) !important;
  border-radius: var(--dna-radius) !important;
  background: var(--dna-surface);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  min-height: 2.75rem;
  border-color: rgba(113, 221, 255, 0.38);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(21, 34, 70, 0.96), rgba(40, 37, 78, 0.96));
  color: white;
  font-weight: 700;
  box-shadow: 0 8px 24px rgba(36, 50, 115, 0.28);
  transition: transform 150ms ease, border-color 150ms ease, box-shadow 150ms ease;
}
[data-testid="stBaseButton-primary"] {
  border-color: rgba(67, 231, 255, 0.6) !important;
  background: linear-gradient(135deg, #147f9c, #6853c7 58%, #a23e92) !important;
  box-shadow: 0 10px 30px rgba(67, 231, 255, 0.16) !important;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1px);
  border-color: var(--dna-cyan);
  box-shadow: 0 10px 28px rgba(67, 231, 255, 0.18);
}
.stButton > button:disabled, [data-testid="stFormSubmitButton"] > button:disabled {
  color: #7e89aa;
  background: rgba(29, 36, 61, 0.76);
  border-color: rgba(126, 137, 170, 0.2);
  box-shadow: none;
}

button:focus-visible, input:focus-visible, textarea:focus-visible,
[role="button"]:focus-visible, [role="checkbox"]:focus-visible {
  outline: 3px solid var(--dna-cyan) !important;
  outline-offset: 3px !important;
}

[data-baseweb="input"] > div, [data-baseweb="textarea"] > div,
[data-baseweb="select"] > div {
  border-color: rgba(132, 156, 255, 0.28) !important;
  border-radius: 12px !important;
  background: rgba(7, 12, 29, 0.72) !important;
}

[data-testid="stAlert"] {
  border-radius: 15px;
  border: 1px solid rgba(132, 156, 255, 0.23);
  background: rgba(15, 22, 48, 0.88);
}

[data-testid="stCode"] { border: 1px solid var(--dna-line); border-radius: 14px; }

@keyframes dna-float {
  0%, 100% { transform: rotate(18deg) translateY(0); }
  50% { transform: rotate(14deg) translateY(-8px); }
}

@media (max-width: 900px) {
  .sdc-hero { grid-template-columns: 1fr; min-height: auto; }
  .sdc-dna-visual { display: none; }
  .sdc-workflow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 520px) {
  .stMainBlockContainer { padding-inline: 0.85rem; padding-top: 1rem; }
  .sdc-hero { padding: 1.3rem; border-radius: 21px; }
  .sdc-hero h1 { font-size: 2.45rem; }
  .sdc-workflow { grid-template-columns: 1fr; }
  .sdc-step { min-height: 82px; }
  .sdc-pill { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
"""


def hero_html(release_label: str, language: Language = "en") -> str:
    safe_label = escape(release_label)
    copy = escape(text(language, "hero.copy"))
    safety_aria = escape(text(language, "hero.safety_aria"))
    selected_only = escape(text(language, "hero.selected_only"))
    human_approval = escape(text(language, "hero.human_approval"))
    local_storage = escape(text(language, "hero.local_storage"))
    rungs = "".join(
        f'<span class="sdc-rung" style="--rung-top:{top}%;--rung-angle:{angle}deg"></span>'
        for top, angle in ((18, -12), (32, 7), (46, 14), (60, -7), (74, -14))
    )
    return f"""
<section class="sdc-hero" aria-labelledby="sdc-product-title">
  <div>
    <div class="sdc-kicker">Local-first knowledge compiler</div>
    <h1 id="sdc-product-title">Skill DNA<br>Compiler</h1>
    <p class="sdc-hero-copy">
      {copy}
    </p>
    <div class="sdc-pill-row" aria-label="{safety_aria}">
      <span class="sdc-pill">{selected_only}</span>
      <span class="sdc-pill">{human_approval}</span>
      <span class="sdc-pill">{local_storage}</span>
      <span class="sdc-pill">{safe_label}</span>
    </div>
  </div>
  <div class="sdc-dna-visual" aria-hidden="true">
    <span class="sdc-strand"></span>
    {rungs}
  </div>
</section>
"""


def workflow_html(language: Language = "en") -> str:
    steps = (
        ("01", "SELECT", text(language, "workflow.select")),
        ("02", "SEQUENCE", text(language, "workflow.payload")),
        ("03", "REVIEW", text(language, "workflow.review")),
        ("04", "COMPILE", text(language, "workflow.compile")),
        ("05", "EXPORT", text(language, "workflow.export")),
    )
    cards = "".join(
        '<div class="sdc-step">'
        f'<span class="sdc-step-number">{number}</span>'
        f"<strong>{label}</strong><span>{description}</span></div>"
        for number, label, description in steps
    )
    aria_label = escape(text(language, "workflow.aria"))
    return f'<nav class="sdc-workflow" aria-label="{aria_label}">{cards}</nav>'


def safety_sidebar_html(
    release_label: str,
    *,
    api_key_configured: bool,
    language: Language = "en",
) -> str:
    key_state = text(
        language,
        "sidebar.key_configured" if api_key_configured else "sidebar.key_missing",
    )
    hidden_state = text(language, "sidebar.key_hidden", state=key_state)
    title = escape(text(language, "sidebar.title"))
    vault_status = escape(text(language, "sidebar.vault"))
    gate_status = escape(text(language, "sidebar.gates"))
    network_status = escape(text(language, "sidebar.network"))
    return f"""
<div class="sdc-side-title">{title}</div>
<div class="sdc-safety-card"><strong>LOCAL VAULT</strong><span>{vault_status}</span></div>
<div class="sdc-safety-card"><strong>HUMAN GATE</strong><span>{gate_status}</span></div>
<div class="sdc-safety-card">
  <strong>API CREDENTIAL</strong><span>{escape(hidden_state)}</span>
</div>
<div class="sdc-safety-card">
  <strong>NETWORK SCOPE</strong><span>{network_status}</span>
</div>
<div class="sdc-build">BUILD {escape(release_label)}</div>
"""


def inject_theme() -> None:
    st.markdown(theme_css(), unsafe_allow_html=True)


def render_hero(release_label: str, language: Language = "en") -> None:
    st.markdown(hero_html(release_label, language), unsafe_allow_html=True)


def render_workflow(language: Language = "en") -> None:
    st.markdown(workflow_html(language), unsafe_allow_html=True)


def render_local_safety_sidebar(
    release_label: str,
    *,
    api_key_configured: bool,
    language: Language = "en",
) -> None:
    with st.sidebar:
        st.markdown(
            safety_sidebar_html(
                release_label,
                api_key_configured=api_key_configured,
                language=language,
            ),
            unsafe_allow_html=True,
        )
