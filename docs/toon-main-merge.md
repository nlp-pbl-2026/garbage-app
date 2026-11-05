# 東温市ブランチへのmain統合（2026-11-05）

`feat/toon-support` の `ccf8234` へ、fetchした `origin/main` の `f03cf60` をマージします。東温市・伊予市PET修正に、mainで完了した大洲市・砥部町・愛南町・鬼北町・松野町・内子町・松前町を加え、13自治体・243選択地区を保持します。

## 競合解消

| ファイル | 統合内容 |
| --- | --- |
| `data/regions/catalog.json` | mainの12自治体と東温市をIDで統合。重複・削除なし |
| `frontend/assets/data/municipality_catalog.json` | mainの全項目を保持し、東温市を追加。部分生成機能で東温市を再生成し、13自治体の版・区分・台帳をバックエンドと比較 |
| `backend/app/services/waste_guide_service.py` | mainの品目名一致候補補助・条件分岐補正と、PETマークの否定・本体/部品の区別・採用根拠の条件判定・大人2人の運搬確認を統合 |
| `README.md` | 東温市と追加7自治体の説明を保持。13自治体と各データの有効期間に更新 |
| `docs/data.md` | 両方のデータガイドと、自治体ごとの取得・配置方針を保持 |
| `infra/README.md` | 東温市の同梱データ・未確認時刻の扱いを残し、標準カタログ全体の配置検証へ統合 |

自動マージされた `scripts/generate_frontend_data.py` でも、mainの部分生成と既存アセットの保持、東温市の `start_time` / `time_note` / `cutoff_status` の両方を確認しました。粗大ごみの `guide_only` 対応、地区台帳消失時のキャッシュ失効、他メンバーの生成・検証スクリプトも保持します。

## 結合によって生じた不具合の修正

- 完全一致補正が、PET本体の説明に現れたキャップの行を採用し、正しいPET判定をプラへ戻すケースを検出しました。一致候補にも明示した本体・取り外した部品の区別を適用します。
- main側の条件判定では、品目固有の注記を区分共通の案内と区別します。元のPET回帰テストの合成キャップ資料も、実際に確認が必要な条件を品目固有注記として記載し、未回答なら質問する検査を維持しました。松山市の既存の先頭根拠の条件ガードは保持します。
- 東温市の大人2人の運搬条件や紙パックの内側など、完全一致補正で処理していない分岐を固定分類で上書きせず、地域資料を使うNova判定と既存の追加質問へ委ねます。
- 「水洗いした／しました／済み」を確認済みの洗浄情報として認識し、八幡浜市のPETへ汚れの質問を再度出さないようにしました。
- 一致候補の既定分類を使う場合も、公式資料の区分共通の出し方・搬出案内を保持します。条件分岐で別区分へ変わる場合に元区分の出し方を転用しません。

`backend/tests/test_merged_regional_search.py` に14件の合成・メタデータ検査を追加しました。実Bedrock・Embedding生成・AWSリソース操作は行っていません。

## テスト結果とデータ不足

追加7自治体のGit管理外CSV・NPZ・カレンダーはこのローカル環境にありません。共有先も不明との回答を受けたため、ダミーの日付・索引や別自治体の情報で補完していません。7自治体の追跡対象のデータ・索引manifestは `origin/main` とバイト単位で同じです。

| 検査 | 結果 |
| --- | --- |
| バックエンド全実行（通常＋公式統合） | 434成功、32失敗。失敗は追加7自治体のデータ不足に限定 |
| データ不足を除いた実行可能なバックエンド範囲 | 434成功、既存の非推奨警告4件 |
| PET保存済み応答のオフライン再生 | 伊予市11例＋既存5自治体各1例、16/16成功。有料API未使用 |
| Flutter通常＋全自治体ツールテスト | 228成功、1失敗。追加7自治体カレンダーの未配置によるもの |
| Flutter解析 | error 0、既存warning 7・info 55（終了コード1） |
| Flutter Webビルド | 成功。既存のアイコンフォント警告あり |
| カタログ・生成メタデータ | 13自治体・243地区。区分・搬出時刻・版・地区台帳の一致を確認 |

バックエンドの未検証内訳は `backend/tests/test_assigned_exact_evidence.py` の17件と、`backend/official_tests/verify_assigned_municipalities_runtime.py` の15件です。テストを削除・スキップ化して成功扱いにはしていません。Flutterでは `tool/verify_assigned_municipalities_data_test.dart` のうち、選択名・粗大ごみ案内・カタログの3件は通り、カレンダー/iCalの1件が不足データで失敗しました。ビルド成功だけで追加7自治体の実動作を確認済みとは扱いません。

主な再実行コマンド（リポジトリルート）:

```bash
backend/.venv/bin/python -m pytest backend/tests backend/official_tests -q \
  --override-ini='python_files=test_*.py verify_*.py'
# 現在配置済みのデータだけで検証できる範囲
backend/.venv/bin/python -m pytest backend/tests \
  --ignore=backend/tests/test_assigned_exact_evidence.py \
  backend/official_tests/verify_toon_runtime.py \
  backend/official_tests/verify_niihama_runtime.py \
  backend/official_tests/verify_ikata_runtime.py \
  backend/official_tests/verify_iyo_runtime.py -q
```

Flutterは保護対象6ファイルへ影響しない一時コピーで `flutter pub get`、`flutter test test tool`、`flutter analyze`、`flutter build web` を実行しました。PET再生は既存のGit管理外モデル応答・検索根拠を使い `/api/search/decide` を通した検査で、新しいモデル応答や変更後の検索順位の実API評価ではありません。

追加7自治体をこの環境で実際に利用するには、[担当7自治体の接続ガイド](assigned-municipalities-completion.md)に従って正規のCSV・NPZ・カレンダーを配置し、生成アセットを整えて上記の全テストを再実行してください。NPZを共有できない場合の有償再生成は、このマージ作業には含めません。
