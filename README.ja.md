<h1 align="center">🧬 Skill DNA Compiler</h1>

<p align="center"><strong>メモを、AIが本当に再利用できる根拠付きSkillへ。</strong></p>

<p align="center">
  明示選択したObsidian・Markdownメモから、人間が確認・承認したCodex Skillを作る
  ローカルファーストのWindowsアプリです。
</p>

<p align="center">
  <a href="https://github.com/johnfreeman13592-lab/skill-dna-compiler/releases/tag/v0.1.0-beta.3"><img alt="リリース" src="https://img.shields.io/github/v/release/johnfreeman13592-lab/skill-dna-compiler?include_prereleases&label=beta&color=7c3aed"></a>
  <img alt="対応OS" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4">
  <a href="LICENSE"><img alt="ライセンス" src="https://img.shields.io/badge/license-MPL--2.0-2563eb"></a>
  <img alt="ローカルファースト" src="https://img.shields.io/badge/data-local--first-059669">
  <img alt="テレメトリーなし" src="https://img.shields.io/badge/telemetry-none-475569">
</p>

<p align="center">
  <a href="README.md">English</a> · <strong>日本語</strong> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

> [!NOTE]
> 👋 **Skill DNA Compilerを見つけてくれてありがとうございます！**
> まだ始まったばかりのプロジェクトです。ぜひBeta版を試して、役に立った点や
> 分かりにくかった点を教えてください。一緒にこれからのSkill DNA Compilerを育てていけたら嬉しいです。

---

## Windows版をダウンロード

> [!IMPORTANT]
> **[Skill DNA Compiler v0.1.0-beta.3 Windows版をダウンロード](https://github.com/johnfreeman13592-lab/skill-dna-compiler/releases/download/v0.1.0-beta.3/skill-dna-compiler-0.1.0-beta.3-windows-x64.zip)**

1. ダウンロードしたZIPを右クリックし、**「すべて展開」**を選ぶ。
2. 展開後のフォルダを開く。ZIPの中から直接起動しない。
3. `Skill DNA Compiler.exe`をダブルクリックする。

最初は同梱の`Sample Vault`と**モック抽出**を使ってください。この手順ではAPIキーが不要で、
外部AIへ何も送信せず、料金もかかりません。SmartScreenや画面の操作順は
[Betaクイックスタート](docs/beta-quick-start.md)で確認できます。

## 何が変わるのか

| これまで | Skill DNA Compilerを使うと |
|---|---|
| 有用な経験が複数のメモへ分散する。 | 選択したメモから再利用候補を作れる。 |
| AIが、元資料にない不足部分を補っても気付きにくい。 | 最終指示を正確な根拠と比較できる。 |
| 生成したSkillを信用してよいか、後から判断しにくい。 | 人間が承認し、版と根拠を保存してから出力できる。 |
| 別プロジェクトで同じ説明を繰り返すことがある。 | 承認したCodex用`SKILL.md`へ手順を持ち運べる。 |

## Skill DNA Compilerの強み

### 🔬 AIの自信より、確認できる根拠

DNA Traceは、最終指示をユーザーが選んだメモの正確な根拠へ接続します。直接根拠がない、
または人間が承認していない指示は、厳格な変換・出力ゲートを通過できません。

### 🧑 人間の承認が必須

抽出、候補承認、Skill DNA化、ファイル出力は別の操作です。候補を勝手に承認したり、
既存の`SKILL.md`を無確認で上書きしたりしません。

### 🔒 最初からローカルファースト

Vaultは読み取り専用です。メモ、候補、Skill DNA、履歴、バックアップ、生成ファイルは
ユーザーのPCへ保存します。アカウント、運営者サーバー、月額課金、ライセンス認証、
自動テレメトリーはありません。

## 使い方

```text
1. メモを選ぶ
       ↓
2. 伏字済みの正確な送信JSONと料金上限を確認する
       ↓
3. 根拠付きのSkill候補を抽出する
       ↓
4. 根拠を読み、信用できる内容だけを承認する
       ↓
5. 版付きSkill DNAとして保存し、Codex用SKILL.mdへ出力する
```

OpenAIを使う実抽出は、利用者自身のAPIキーと料金を使用します。有料処理の前には、正確な
送信JSONと保守的な料金上限を別々に確認します。選択していないメモは送信対象になりません。

## 一般公開Betaの状態

現在はWindows限定の一般公開Betaです。Obsidian・MarkdownからCodex Skillを作る一連の流れ、
指示単位の根拠確認、ローカルデータ保護、Windows Credential Manager、Python同梱の
ポータブルZIPを実装しています。

3種類の実メモで抽出し、人間が確認した4件のSkillを架空ケースで前方テストしました。公開した
Windows候補はchecksum、ZIP安全性、packaged import、HTTP health、検証対象プロセスの
`127.0.0.1`限定通信に合格しています。これはBetaとしての技術的証拠であり、幅広い利用価値や
すべてのPCでの互換性を証明するものではありません。

正確な証拠と制限は
[一般公開Beta準備監査](docs/public-beta-readiness-audit-2026-07-22.md)にあります。

## 現在の対応範囲

| 項目 | 現在 | 実際の需要を確認して追加 |
|---|---|---|
| 入力 | 明示選択したObsidian・Markdownメモ | 他のメモアプリ、テキスト形式、会話・行動・Git履歴 |
| 出力 | Codex互換`SKILL.md` | 他のAIエージェント、人間向け形式 |
| OS | Windows 10/11 x64 | 他のデスクトップOS |
| 保存 | ローカルSQLite、ローカルファイル、検証付きバックアップ | 現段階で大規模クラウド基盤の予定なし |

最初の製品は意図的に狭くしています。一方でUI、ドメインロジック、保存、安全性、OS固有処理、
OpenAI連携を分離し、将来のadapter追加で安全境界を書き直さない構造を維持します。

## 安全性とプライバシー

- 外部送信対象になるのは、明示選択したメモだけです。
- タイトル、相対パス、本文をローカルで検査・伏字します。
- 検出0件を安全の保証とは扱わず、正確なJSONの人間確認を残します。
- OpenAIはStructured Outputsと`store=False`を使用します。
- 配布版のAPIキーはWindows Credential Managerだけへ保存し、再表示しません。
- APIキーとメモ本文をSQLiteや通常ログへ保存しません。
- 出力はユーザーが承認した既存フォルダ内に限定し、原子的に置換します。
- DBのバックアップと復元時にSQLite整合性を検査します。

詳細は[プライバシーとAPI送信](docs/privacy.md)を参照してください。

## 開発

<details>
<summary><strong>ローカル開発コマンド</strong></summary>

必要環境はWindows 10/11とPython 3.11以上です。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,package]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m streamlit run app.py
```

開発用の秘密情報はGit管理外の`.env.local`へ置きます。APIキーをソース、Issue、ログ、
生成Skillへ書かないでください。

</details>

<details>
<summary><strong>Windowsパッケージの作成と検証</strong></summary>

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\build_windows_beta.ps1

.\.venv\Scripts\python.exe .\tools\verify_windows_candidate.py `
  .\dist\skill-dna-compiler-0.1.0-beta.3-windows-x64.zip `
  --report-dir .\build\verification\beta.3
```

検証ツールはchecksum、ZIP制限と安全なパス、必須・禁止ファイル、依存関係とライセンス、
packaged import、HTTP health、プロセス所有権、loopback限定listenerを確認します。
終了コードは合格`0`、検証不合格`1`、ツールを実行できない場合`2`です。

</details>

## ドキュメント

- [Betaクイックスタート](docs/beta-quick-start.md)
- [プライバシーとAPI送信](docs/privacy.md)
- [アーキテクチャと安全境界](docs/architecture.md)
- [実装計画](docs/implementation-plan.md)
- [Beta検証チェックリスト](docs/beta-test-checklist.md)

## フィードバックと開発参加

- 質問・提案は[Discussions](https://github.com/johnfreeman13592-lab/skill-dna-compiler/discussions)
- 再現可能な不具合は[Issues](https://github.com/johnfreeman13592-lab/skill-dna-compiler/issues)
- セキュリティ問題はGitHubの非公開脆弱性報告
- 変更を送る前に[CONTRIBUTING.md](CONTRIBUTING.md)を確認

## ライセンス

Skill DNA Compilerは[Mozilla Public License 2.0](LICENSE)で公開しています。依存ライブラリの
ライセンスとnoticeは[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。
