# Skill DNA Compiler

Skill DNA Compilerは、ユーザーが選択したObsidianのMarkdownメモから、別のプロジェクトでも再利用できる手順やルールを抽出し、人間の承認を経てCodex用`SKILL.md`へ変換するローカルアプリです。

## 現在の状態

2026-07-22時点で、Windows限定の一般公開Betaです。Obsidian／Markdown
からCodex用Skillを作る一連の流れ、指示ごとの根拠確認、初心者向けレビュー画面、ローカル
データ保護、Windows Credential Manager、Python同梱のポータブルZIPを実装しています。

3種類の実メモで抽出と人間レビューを行い、承認した4件のSkillを別の架空ケースでも前方
テストしました。現在の限定RCは、checksum、ZIP安全性、packaged import、HTTP health、
`127.0.0.1`限定通信を含む12項目のオフライン検証に合格しています。現時点で確認済みの
アプリ機能上の公開停止問題は0件です。配布候補には82パッケージのlicense manifest、収集済み
license／notice、Streamlitの固定された公式LICENSE／NOTICESも含めて検証しています。

ソースは履歴を分離した[公開リポジトリ](https://github.com/johnfreeman13592-lab/skill-dna-compiler)で
MPL-2.0として公開し、Windows版はGitHubのPre-releaseから配布します。質問・提案は
Discussions、不具合はIssues、脆弱性は非公開報告を使用してください。オフライン検証だけを
一般ユーザーへの価値証明とは扱いません。詳細な証拠は[一般公開Beta準備監査](docs/public-beta-readiness-audit-2026-07-22.md)を参照してください。

公開後に検証する機能仮説と優先順位は[Post-Betaロードマップ](docs/post-beta-roadmap.md)に
まとめています。これは確約された日程ではなく、利用者のフィードバックで更新します。

## 初めて使う方へ

最初はOpenAI APIキーを用意せず、同梱のサンプルだけで無料確認できます。

1. ZIPを展開し、`Skill DNA Compiler.exe`を起動する。
2. `Sample Vault`を選び、料金のかからない「モック抽出」を試す。
3. 候補の根拠を確認し、よいものだけを承認してCodex用`SKILL.md`へ保存する。

ここまで外部AIへの送信とAPI料金はありません。実際のメモで有料抽出するときだけ、送信する
JSONと料金上限を確認し、内容と料金の2つへ別々に同意します。選択していないメモは送信対象に
なりません。詳しい画面順は[Betaクイックスタート](docs/beta-quick-start.md)にあります。

### よく出る言葉

- `Vault`：ObsidianのMarkdownメモが入ったフォルダです。
- `候補`：メモから抽出した、再利用できそうな手順やルールです。
- `根拠の確認`：候補の指示が元メモのどこに基づくか、人が確かめる工程です。
- `Skill DNA`：承認した候補を、版と根拠付きで保存したものです。
- `SKILL.md`：Codexが読み込める最終ファイルです。

迷ったときは、実メモやAPIキーを使わずに`Sample Vault`とモック抽出へ戻れば、料金を発生
させずに操作を確認できます。

## 製品方針

- 無料のローカルアプリとして配布する
- アカウント、月額課金、ライセンス認証、運営者サーバーをMVPへ含めない
- メモ、候補、Skill DNA、生成Skillは原則としてユーザーのPCへ保存する
- AIへ送るのはユーザーが選択し、送信前に確認した文章だけにする
- OpenAI APIは利用者自身のAPIキーと利用料金で使用する
- Skill候補は自動承認せず、人間の確認を必須にする

詳細は[実装計画](docs/implementation-plan.md)、[アーキテクチャ](docs/architecture.md)、[プライバシーとAPI送信](docs/privacy.md)を参照してください。

## Betaの起動

生成済みZIPを展開し、`Skill DNA Compiler.exe`を起動します。Pythonのインストールは不要です。初回操作、SHA-256確認、SmartScreen、アンインストールは[Betaクイックスタート](docs/beta-quick-start.md)を参照してください。

別Windows PCでの最終確認には[Beta検証チェックリスト](docs/beta-test-checklist.md)を使います。既存Pythonを削除する必要はありません。
完成時の証拠と既知の制限は[Beta完成監査](docs/beta-completion-audit.md)に記録しています。

## 開発環境

- Windows 10/11（最初の配布対象）
- Python 3.11以上

初回完成版はWindows専用です。将来はWindows以外のデスクトップOSにも広げる方針ですが、
Linux系OSとmacOSは例であり、現時点の固定された次期対象や動作保証ではありません。
共通の変換・検証ロジックとOS固有の資格情報・ランチャー・配布処理を分離し、Windows版を
完成させてから実際の需要に応じてOS adapterと受入テストを追加します。

開発・検証時はPowerShellで次を実行します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,package]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m streamlit run app.py
```

現在の検証では、引用検証、SQLiteの外部キー、候補レビュー、Skill DNA化と版履歴、出力先境界、無確認上書き拒否、出力履歴、Responses APIの`store=False`構造化リクエストを自動テストしています。生成したUTF-8の`SKILL.md`はCodexの`skill-creator`付属検証器でも有効と確認済みです。

ネットワーク不要のサンプルVault E2Eは、読込から伏字、候補、承認、Skill DNA、`SKILL.md`出力までを固定期待値で検証します。Betaでは資格情報ストア、二重起動防止、localhost限定起動、配布ランチャーのテストも追加しています。

開発時のAPIキーはGit管理外の`.env.local`に置きます。Beta版では設定画面からWindows Credential Managerへ保存し、平文ファイルへフォールバックしません。キーをREADME、ソースコード、Issue、ログへ貼り付けないでください。

## Betaパッケージの作成

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\build_windows_beta.ps1
```

`dist`へ`skill-dna-compiler-0.1.0-beta.2-windows-x64.zip`と`.sha256`を生成します。完成済みの`beta.1`成果物は上書きしません。成果物はGit管理外です。

既存成果物は同名で上書きしません。開発中の別名検証物は、たとえば
`-ArtifactLabel 0.1.0-beta.2-dogfood-20260721`を付けて作成します。

## Windows候補ZIPのオフライン検証

成果物のchecksum、内容、依存関係、packaged import、HTTP health、loopback限定通信を一括確認できます。検証中のDBと資格情報は一時領域へ隔離され、既存レポートは上書きしません。

```powershell
.\.venv\Scripts\python.exe .\tools\verify_windows_candidate.py `
  .\dist\skill-dna-compiler-0.1.0-beta.2-windows-x64.zip `
  --report-dir .\build\verification\beta.2
```

終了コードは、合格`0`、検証不合格`1`、ツール自体を実行できない場合`2`です。JSONとMarkdownの両方へ証拠を保存します。

## データ保存

SQLiteデータベースの既定保存先はOSのユーザーデータ領域です。バックアップはDBの隣の`skill-dna.db.backups`へ保存され、作成・復元時にSQLiteの整合性を検査します。古い未バージョンDBをv1へ移行する前と、手動復元の直前には自動で安全バックアップを作ります。Vaultの元ファイルは変更しません。

## リポジトリ運用

`.env.local`、SQLite、生成Skill、ビルド成果物はGit管理外です。内部開発リポジトリの履歴は
公開せず、監査済みallowlistから作る履歴なしの公開リポジトリを使用します。

## License

Skill DNA CompilerのソースコードはMozilla Public License 2.0（MPL-2.0）で公開しています。
全文は[LICENSE](LICENSE)、依存ライブラリは[Third-party notices](THIRD_PARTY_NOTICES.md)を
参照してください。
