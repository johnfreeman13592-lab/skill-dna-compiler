"""Self-contained simulated walkthrough for the guided Home screen."""

# ruff: noqa: E501

from __future__ import annotations

import base64
import json

from .i18n import Language

_COPY = {
    "en": {
        "label": "SIMULATION · SAMPLE DATA ONLY",
        "title": "Watch a complete example",
        "lead": (
            "See the path from choosing your notes to finishing the Skill file."
        ),
        "disclaimer": (
            "This explanation does not read notes, change app state, send data, "
            "or write files."
        ),
        "previous": "Previous",
        "next": "Next",
        "pause": "Pause",
        "resume": "Resume",
        "choose": "Choose scene",
        "scene": "Scene",
        "example": "Current example",
        "draft": "Skill draft",
        "reviewed": "Reviewed before continuing",
        "separate": "Separate confirmation",
        "steps": [
            (
                "Start · Use my notes",
                "Choose how to begin",
                "The personal-note path starts only after you select it.",
                "Try the sample",
                "Use my notes",
            ),
            (
                "Step 1 · Choose notes",
                "Select only the notes to use",
                "Load a folder, select safe-changes.md, then continue.",
                r"C:\My Notes",
                "Continue with selected notes",
            ),
            (
                "Step 2 · Check data",
                "Confirm the exact data",
                "Review the redacted JSON and local mode before creating drafts.",
                '{"notes":["safe-changes.md"],"content":"Back up before changing data."}',
                "Create draft Skills locally",
            ),
            (
                "Step 3 · Review draft",
                "Compare the draft with its source",
                "Check support, meaning, impact, and safety before approval.",
                "Before changing important data, create and verify a backup.",
                "Approve",
            ),
            (
                "Step 4 · Save twice",
                "Save the Skill, then save the file",
                "The local Skill version and SKILL.md use separate confirmations.",
                r"C:\My Skills\safe-data-change\SKILL.md",
                "Save SKILL.md",
            ),
            (
                "Complete · Finish",
                "The Skill file is ready",
                "Confirm the result path, then finish the guided flow.",
                r"C:\My Skills\safe-data-change\SKILL.md",
                "Exit",
            ),
        ],
    },
    "ja": {
        "label": "シミュレーション・サンプルデータのみ",
        "title": "実際の流れを最後まで見る",
        "lead": "自分のメモを選んでからSkillファイルを完成させるまでを確認できます。",
        "disclaimer": (
            "この説明はメモを読み取らず、アプリの状態を変えず、"
            "データ送信やファイル保存も行いません。"
        ),
        "previous": "前へ",
        "next": "次へ",
        "pause": "一時停止",
        "resume": "再開",
        "choose": "場面を選ぶ",
        "scene": "場面",
        "example": "現在の例",
        "draft": "Skill案",
        "reviewed": "続ける前に確認",
        "separate": "別の確認操作",
        "steps": [
            (
                "開始・自分のメモを使う",
                "開始方法を選ぶ",
                "「自分のメモを使う」を選んだ後にだけ操作が始まります。",
                "Sampleで試す",
                "自分のメモを使う",
            ),
            (
                "Step 1・メモを選ぶ",
                "使用するメモだけを選ぶ",
                "フォルダーを読み込み、safe-changes.mdだけを選んで進みます。",
                r"C:\My Notes",
                "選んだメモで続ける",
            ),
            (
                "Step 2・データを確認",
                "正確なデータを確認する",
                "Skill案を作る前に、隠したJSONとローカルモードを確認します。",
                '{"notes":["safe-changes.md"],"content":"変更前にバックアップする。"}',
                "ローカルでSkill案を作る",
            ),
            (
                "Step 3・Skill案を確認",
                "Skill案を元メモと照らし合わせる",
                "根拠、意味、影響、安全条件をそれぞれ確認してから承認します。",
                "重要なデータを変更する前にバックアップを作成して確認する。",
                "承認する",
            ),
            (
                "Step 4・2回の保存",
                "Skillを保存してからファイルを保存",
                "ローカルのSkill版とSKILL.mdは別々に確認して保存します。",
                r"C:\My Skills\safe-data-change\SKILL.md",
                "SKILL.mdを保存",
            ),
            (
                "完了・終了",
                "Skillファイルの準備ができました",
                "結果の保存先を確認してから、初回ガイドを終了します。",
                r"C:\My Skills\safe-data-change\SKILL.md",
                "終了",
            ),
        ],
    },
}


def build_guided_walkthrough_html(language: Language) -> str:
    """Return an isolated six-scene simulation in English or Japanese."""

    selected_language = "ja" if language == "ja" else "en"
    copy = _COPY[selected_language]
    copy_json = json.dumps(copy, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="{selected_language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#07101d;--card:#111d30;--line:#334966;--text:#f4f7fc;
--muted:#b7c4d6;--cyan:#63e6ed;--green:#67e0ac}}
*{{box-sizing:border-box}}body{{margin:0;background:transparent;color:var(--text);
font:15px/1.5 "Segoe UI","Yu Gothic UI",sans-serif}}
button{{min-height:40px;border:1px solid var(--line);border-radius:10px;
padding:.55rem .85rem;background:#17263d;color:var(--text);cursor:pointer}}
button:hover,button:focus-visible{{border-color:var(--cyan);outline:none}}
.tour{{border:1px solid var(--line);border-radius:16px;padding:1rem;
background:linear-gradient(145deg,#07111f,#0b1c31)}}
.head{{display:flex;justify-content:space-between;gap:1rem;align-items:end}}
.label{{color:var(--cyan);font-size:.75rem;font-weight:800;letter-spacing:.08em}}
h2{{margin:.25rem 0;font-size:clamp(1.35rem,3vw,2rem)}}p{{margin:.3rem 0;color:var(--muted)}}
.disclaimer{{max-width:440px;padding:.6rem;border:1px solid #327255;border-radius:10px}}
.stage{{position:relative;min-height:430px;margin-top:1rem;overflow:hidden;
border:1px solid var(--line);border-radius:14px;background:#050c16}}
.slide{{display:none;min-height:430px;padding:1rem}}.slide.active{{display:block}}
.top{{display:flex;justify-content:space-between;gap:.6rem;padding:.55rem .7rem;
border:1px solid #263d59;border-radius:9px;background:#091625}}
.step{{color:var(--cyan);font-weight:800}}.body{{width:min(900px,100%);margin:1.2rem auto}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-top:1rem}}
.card{{padding:1rem;border:1px solid var(--line);border-radius:12px;background:var(--card)}}
.field,.control,.target{{display:block;margin:.65rem 0;padding:.65rem .75rem;
border:1px solid #3a5271;border-radius:8px;background:#081526;color:#dbe7f6}}
.field{{font:13px/1.4 Consolas,monospace;overflow-wrap:anywhere}}
.check{{color:var(--green)}}.target{{display:inline-block;position:relative;
border-color:var(--cyan);box-shadow:0 0 0 3px #63e6ed2b,0 0 24px #63e6ed26;
font-weight:800;background:#167c85}}
.pointer{{position:absolute;z-index:3;left:calc(100% + 40px);top:-26px;
width:0;height:0;border-top:20px solid white;border-right:12px solid transparent;
filter:drop-shadow(0 2px 3px #000);transform:rotate(-12deg)}}
.ripple{{position:absolute;z-index:2;left:50%;top:50%;width:38px;height:38px;
margin:-19px;border:3px solid var(--cyan);border-radius:50%;opacity:0}}
.slide.active .pointer{{animation:pointer 5s ease-in-out infinite}}
.slide.active .ripple{{animation:ripple 5s ease-out infinite}}
@keyframes pointer{{0%,18%{{left:calc(100% + 40px);top:-26px}}
52%,100%{{left:50%;top:50%;transform:translate(-2px,-3px) rotate(-12deg)}}}}
@keyframes ripple{{0%,53%{{transform:scale(.25);opacity:0}}58%{{opacity:.9}}
72%,100%{{transform:scale(1.35);opacity:0}}}}
.controls{{display:flex;align-items:center;justify-content:center;gap:.55rem;
flex-wrap:wrap;margin-top:.8rem}}.dots{{display:flex;gap:.4rem}}
.dot{{width:12px;height:12px;min-height:12px;padding:0;border-radius:50%;background:#52657e}}
.dot.active{{background:var(--cyan);box-shadow:0 0 0 3px #63e6ed22}}
.status{{display:flex;align-items:center;gap:.55rem;min-width:180px;font-weight:800}}
.progress{{height:7px;flex:1;border-radius:99px;background:#263951;overflow:hidden}}
.progress span{{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),var(--green))}}
@media(max-width:680px){{.head,.grid{{display:block}}.disclaimer{{margin-top:.7rem}}
.stage,.slide{{min-height:500px}}}}
@media(prefers-reduced-motion:reduce){{.slide.active .pointer,.slide.active .ripple{{animation:none}}
.pointer{{left:50%;top:50%;transform:translate(-2px,-3px) rotate(-12deg)}}.ripple{{display:none}}}}
</style>
</head>
<body>
<section class="tour" aria-roledescription="carousel">
  <div class="head">
    <div><div class="label" id="label"></div><h2 id="title"></h2><p id="lead"></p></div>
    <p class="disclaimer" id="disclaimer"></p>
  </div>
  <div class="stage" id="stage" tabindex="0"></div>
  <div class="controls">
    <button id="previous" type="button"></button>
    <div class="dots" id="dots" role="group"></div>
    <button id="next" type="button"></button>
    <button id="pause" type="button" aria-pressed="false"></button>
    <div class="status"><span id="counter">1 / 6</span>
      <span class="progress" aria-hidden="true"><span id="bar"></span></span>
    </div>
  </div>
</section>
<script>
const COPY={copy_json};
let index=0,timer=0,paused=false;
const stage=document.getElementById("stage"),dots=document.getElementById("dots");
document.getElementById("label").textContent=COPY.label;
document.getElementById("title").textContent=COPY.title;
document.getElementById("lead").textContent=COPY.lead;
document.getElementById("disclaimer").textContent=COPY.disclaimer;
function escapeHtml(value){{const node=document.createElement("div");node.textContent=value;return node.innerHTML}}
COPY.steps.forEach((scene,i)=>{{
  const article=document.createElement("article");article.className="slide";article.dataset.scene=String(i);
  article.innerHTML=`<div class="top"><strong>◇ Skill DNA Compiler</strong><span class="step">${{escapeHtml(scene[0])}}</span></div>
  <div class="body"><h3>${{escapeHtml(scene[1])}}</h3><p>${{escapeHtml(scene[2])}}</p>
  <div class="grid"><div class="card"><strong>${{i===2?"JSON":i===3?COPY.draft:COPY.example}}</strong>
  <div class="field">${{escapeHtml(scene[3])}}</div><span class="target">${{escapeHtml(scene[4])}}
  <span class="pointer" aria-hidden="true"></span><span class="ripple" aria-hidden="true"></span></span></div>
  <div class="card"><strong class="check">✓ ${{i<4?COPY.reviewed:COPY.separate}}</strong>
  <p>${{escapeHtml(COPY.disclaimer)}}</p></div></div></div>`;
  stage.append(article);
  const dot=document.createElement("button");dot.className="dot";dot.type="button";
  dot.dataset.index=String(i);dot.setAttribute("aria-label",`${{COPY.choose}} ${{i+1}}`);
  dot.addEventListener("click",()=>show(i,true));dots.append(dot);
}});
function stop(){{if(timer){{clearInterval(timer);timer=0}}}}
function start(){{stop();if(!paused)timer=setInterval(nextScene, 5000)}}
function show(next,manual=false){{
  index=(next+COPY.steps.length)%COPY.steps.length;
  document.querySelectorAll(".slide").forEach((node,i)=>node.classList.toggle("active",i===index));
  document.querySelectorAll(".dot").forEach((node,i)=>{{
    node.classList.toggle("active",i===index);node.setAttribute("aria-pressed",String(i===index));
  }});
  document.getElementById("counter").textContent=`${{index+1}} / ${{COPY.steps.length}}`;
  document.getElementById("bar").style.width=`${{((index+1)/COPY.steps.length)*100}}%`;
  if(manual)start();
}}
function nextScene(){{show(index+1)}}
document.getElementById("previous").textContent=`← ${{COPY.previous}}`;
document.getElementById("next").textContent=`${{COPY.next}} →`;
document.getElementById("previous").addEventListener("click",()=>show(index-1,true));
document.getElementById("next").addEventListener("click",()=>show(index+1,true));
const pause=document.getElementById("pause");
function renderPause(){{pause.textContent=paused?COPY.resume:COPY.pause;pause.setAttribute("aria-pressed",String(paused))}}
pause.addEventListener("click",()=>{{paused=!paused;renderPause();start()}});
document.addEventListener("visibilitychange",()=>document.hidden?stop():start());
show(0);renderPause();start();
</script>
</body>
</html>"""


def build_guided_walkthrough_data_uri(language: Language) -> str:
    """Wrap the walkthrough in a self-contained iframe source."""

    encoded = base64.b64encode(
        build_guided_walkthrough_html(language).encode("utf-8")
    ).decode("ascii")
    return f"data:text/html;base64,{encoded}"
