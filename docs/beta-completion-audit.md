# Skill DNA Compiler v0.1.0-beta.1 完成監査

監査日: 2026-07-20  
判定: 今回定義した一般公開前の非公開Beta MVPとして完成

## 完成物

- Windows 10/11 x64向けポータブルZIP
- ファイル名: `skill-dna-compiler-0.1.0-beta.1-windows-x64.zip`
- サイズ: 93,520,502 bytes（約89.19 MiB）
- SHA-256: `16d3167be48cd8fe4c2ab1b5809fa4f1c459959c18283a71c8a87c479c4bcd8e`
- Python未導入でも使えるPyInstaller `onedir`構成
- 運営者サーバー、アカウント、課金、ライセンス認証、自動テレメトリーなし

## 自動検証

- `pytest`: 103 passed、2 skipped
- `ruff check .`: passed
- `pip check`: no broken requirements
- ZIPと`.sha256`の一致を確認
- PATHを`C:\Windows\System32;C:\Windows`だけに制限し、`where python`でPythonが見つからない状態から展開版EXEのインポート検査に成功
- 配布物内の`.env`、SQLite/DB、想定外の`SKILL.md`、実資格情報らしい値が0件
- Credential Managerへテストキーを保存した後も、SQLiteファイルのバイト列にキーが存在しないことを確認
- `127.0.0.1`限定起動、二重起動防止、秘密情報伏字、選択メモ限定Payload、引用照合、安全なSkill出力を自動テスト

意図したスキップ:

- 実API E2Eは自動実行すると料金と外部通信が発生するためopt-in。別PCで手動実行済み。
- Windows環境でシンボリックリンク作成権限がないテスト1件。シンボリックリンク拒否ロジック自体は実装済み。

## 別Windows PCの手動受入

- ZIPと展開フォルダをセキュリティソフトで確認
- 日本語ユーザー名と空白を含む展開先からEXEを起動
- Streamlit画面を`127.0.0.1`で表示
- APIキーなしで同梱`Sample Vault`を読み込み
- モック抽出1件、候補レビュー、明示承認、Skill DNA `0.1.0`保存、`SKILL.md`出力に成功
- 架空資格情報をCredential Managerへ保存し、再起動後の設定済み表示、非再表示、明示削除に成功
- 実APIキーをCredential Managerへ保存。キー文字列は共有・記録していない
- 架空メモ1件だけの送信JSONと料金上限を確認し、実APIを1回だけ実行
- 実API結果: 候補1件、入力605、出力317、合計922 tokens、料金推定`$0.0062675`
- サンプルDBとテスト出力を削除し、実APIキーだけを保持した空の実利用状態へ復帰

## 安全性とデータ境界

- APIキーはWindows Credential Managerだけへ保存し、SQLite・ログ・生成Skillへ保存しない
- メモ全文はDBへ保存せず、文書メタデータ、候補、検証済み引用など必要なローカルデータだけを保存
- AIへ送るのはユーザーが明示選択し、伏字済みJSONを確認したメモだけ
- 候補は自動承認せず、承認とSkill DNA化とファイル出力を別操作にする
- 出力先は既存の明示フォルダ内へ限定し、上書きには追加確認を要求する

## 既知の制限

- 一般公開前の非公開Betaであり、GitHub Releasesには公開していない
- Windows x64のみ。macOSとLinuxは未対応
- インストーラーではなくポータブルZIP
- コード署名がないため、SmartScreenやウイルス対策ソフトが再生成EXEを確認・ブロックする場合がある
- コンソールを閉じるとアプリも終了する
- Streamlit UIであり、ブラウザーを使用する
- OpenAI API料金はユーザー負担で、表示額はローカル推定

## MVP完成後の運用

- 実際のObsidianメモを少量ずつ明示選択して使用を開始する
- 送信JSONと料金上限の目視確認を省略しない
- 生成Skillの利用結果をローカルフィードバックへ記録する
- 失敗は「現象・原因・修正・検証・再発防止」でObsidianへ残す
- 一般公開前に、OSSライセンス、GitHub公開、Releases、インストーラー、コード署名、主要フィードバック窓口を別途決定する
