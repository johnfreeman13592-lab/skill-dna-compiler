# 一般公開Beta準備監査 — 2026-07-22

## 結論

Windows x64向けポータブルBetaの技術的な配布候補は完成した。初心者向けの最短導線を
`README.txt`としてZIP直下へ追加し、依存license manifestと必要なnoticeを同梱した。
オフライン検証12項目はすべて合格し、現在確認済みのコード上の公開停止問題は0件である。

公開方針は、履歴なしの新規公開リポジトリ、MPL-2.0、`v0.1.0-beta.2` Pre-release、
Discussions／Issues／非公開の脆弱性報告窓口で合意した。この監査記録を作成した時点では
一般公開、push、Release作成を行っておらず、実行には別の明示確認を必要とした。オフライン
検証だけを一般ユーザーへの価値証明とも扱わない。

## 配布候補

- ファイル: `skill-dna-compiler-0.1.0-beta.2-license-manifest-20260722-windows-x64.zip`
- サイズ: 94,068,994 bytes
- SHA-256: `BF5409A0D64AF35B70BF372F651B646920336D7DE56F62DE4367D679F69C0F1C`
- ZIP entries: 2,326
- 展開後サイズ: 224,280,090 bytes
- 依存パッケージ: 82
- 形式: Python同梱、未署名、インストーラーなしのポータブルZIP

SHA-256 sidecar:

`skill-dna-compiler-0.1.0-beta.2-license-manifest-20260722-windows-x64.zip.sha256`

## 初心者向け導線

- リポジトリREADMEの現在地を、限定RCとdogfood完了後の状態へ更新した。
- 「初めて使う方へ」で、APIキーなし・料金なしの3段階を最初に案内した。
- Vault、候補、根拠の確認、Skill DNA、`SKILL.md`を平易に説明した。
- 同梱クイックスタートへ「最初の10分」「困ったとき」を追加した。
- クイックスタートをZIP直下の`README.txt`にも配置し、展開直後に見つけられるようにした。
- ZIP直下、`docs`内、リポジトリ内のクイックスタートがバイト単位で一致することを確認した。
- 今後の候補ZIPでは`README.txt`を必須ファイルとして検証する。

## License／notice監査

- build inventoryの82パッケージをinstalled metadataと照合した。
- 141個のlicense／noticeファイルを自動収集し、SHA-256付きmanifestへ記録した。
- wheelにlicenseファイルがないStreamlit 1.59.2は、公式`LICENSE`と`NOTICES`を版固定で
  同梱し、ビルド前にSHA-256を照合した。
- ZIP直下のMPL-2.0 `LICENSE`、Streamlit 2ファイル、82パッケージmanifestを候補検証の
  必須ファイルにした。
- dependency inventoryとmanifestのpackage名は完全一致した。
- manifestに記録した全141ファイルのZIP内存在、byte数、SHA-256を再照合した。

## 合格したオフライン検証

1. SHA-256 sidecar一致
2. ZIP上限、圧縮率、暗号化有無
3. ZIP CRC
4. 絶対パス、path traversal、symlink不在
5. 重複entry不在
6. 単一root構造
7. `README.txt`を含む必須ファイル
8. 秘密情報、DB、生成Skillなど禁止ファイル不在
9. 依存inventory
10. packaged import smoke
11. Streamlit root／health
12. 所有プロセスのlistenerが`127.0.0.1`限定

runtime検証では`OPENAI_API_KEY`を環境から除去し、検証ツール固有の一時DBとNull keyringを
使用した。実ユーザーDBとWindows Credential Managerは検査対象にしていない。

検証レポート:

- `build/verification/license-manifest-20260722/skill-dna-compiler-0.1.0-beta.2-license-manifest-20260722-windows-x64.zip.verification.json`
- `build/verification/license-manifest-20260722/skill-dna-compiler-0.1.0-beta.2-license-manifest-20260722-windows-x64.zip.verification.md`

## Dogfoodと独自価値の証拠

- 3入力グループで抽出を完了した。
- 実APIは、毎回別のJSONと料金上限を明示承認した3回だけ実行した。実測合計は
  `$0.0640575`。
- 5件の候補のうち4件を厳格レビュー後に承認し、1件を保留した。
- 承認した4件のSkill DNA `0.1.0`は、別の架空ケースによる前方テスト後にCodexへ
  非上書きで導入した。
- 指示単位の根拠確認、安全境界、未確認指示の出力拒否を維持した。

同一ユーザーと同一PCを中心としたdogfoodであり、別ユーザーによる使いやすさ・価値評価の
代替ではない。この限界は公開時に明記し、初期フィードバックで確認する。

## 既存成果物の維持

新しい別名候補の生成後も、既存7 ZIPのSHA-256は不変だった。

- beta.1: `16D3167BE48CD8FE4C2AB1B5809FA4F1C459959C18283A71C8A87C479C4BCD8E`
- beta.2: `3A63357799F9AAC656313FB37EDD2371B0D6D0E778AD541EDD95E811674B6AD9`
- dogfood: `655BA6DAB3150C02160FA153DC0F57F2A66158C2168B5AC1784F2BDA2C2B6C81`
- RC hardening: `37C23CB2857EBA14FFC29D4B8A9799A248D0BC2D66363B0E2DC975AA0D925A72`
- limited RC: `78DF0F3D71D3BEA0566DF35DE9DA0BF0132BA75A95123D1E9BDB51508656C20A`
- onboarding RC: `3AD590B93B185A7DAA1902FC53EF8032FE24635709E03250D296B55E21F684D6`
- public-licenses candidate: `C394A7DB3BB5A10028D083961260FE5F9FB1DF9C9D58D8DB8B0D6D4C7A342F1A`

## 公開前に残る作業

1. 監査済みallowlistから履歴なしの公開用treeを確定する。
2. 公開名から`license-manifest-20260722`を外した最終成果物を公開用commitから再作成する。
3. 公開直前プレビューをユーザーが確認する。
4. 明示承認後にだけ、公開リポジトリ、push、Pre-release、フィードバック窓口を作成する。

外部へ影響する4はユーザーの明示確認後に別作業として行う。インストーラー、コード署名、
macOS/Linux、追加の入力・出力adapterは最初の公開Betaを妨げない。

## 既知の制限

- Windows 10/11 x64限定。
- 未署名のためSmartScreenやウイルス対策ソフトが確認・停止する可能性がある。
- インストーラーではなくポータブルZIP。
- Streamlitをローカルブラウザーで表示し、起動ウィンドウを閉じると終了する。
- OpenAI API料金は利用者負担で、表示額は保守的なローカル推定。
- 自動テレメトリー、クラウド同期、自動承認、自動Skill出力はない。
