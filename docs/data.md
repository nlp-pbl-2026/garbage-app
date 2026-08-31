# データ配置ガイド

本システムは自治体ごとの分別データを差し替えることで、対象地域を拡張できる設計です。
データは `data/regions/<自治体>/` 以下に配置します（`matsuyama` は一例）。

## ディレクトリ構成

```
data/regions/<自治体>/
├── common/knowledge/            # 自治体共通の分別データ
│   ├── items.csv                # 品目辞典（検索対象・正解ラベルの源泉）
│   ├── items.csv.metadata.json  # CSV取り込み方式を試した際のサイドカー
│   ├── category_rules.csv       # 分類区分ごとのルール
│   ├── general_rules.csv        # 一般ルール（排出方法など）
│   ├── *.csv.metadata.json      # 各CSVのサイドカー
│   └── item_embeddings.npz      # 自前Embedding用索引（将来切替・比較実験用）
└── <地区>/calendar/
    └── <年>.csv                 # その地区の収集カレンダー
```

## 各ファイル

### `items.csv`（必須）
品目辞典。あいまい検索の対象であり、評価の正解ラベルの源泉。1行=1品目。

| 列 | 内容 |
| --- | --- |
| `search_text` | 検索・Embedding対象テキスト（通常は品目名） |
| `item_id` | 一意なID |
| `item` | 品目名 |
| `reading` | 読み（任意） |
| `note` | 出し方・注意・分岐条件 |
| `category` | 分類コード（下記9区分のいずれか） |
| `category_display` | 分類の表示名 |
| `rule_ref`, `source_*`, `verification_status` | 出典・検証情報（任意） |

**分類コード（9区分）**: `可燃` / `埋立` / `金・ガ` / `紙類` / `ペット` / `プラ` / `水銀` / `粗大` / `禁止`
（表示名は `backend/app/services/waste_guide_service.py` の `CATEGORY_NAMES` で対応付け。区分体系が異なる自治体を追加する場合はここも更新する。）

### `category_rules.csv` / `general_rules.csv`（推奨）
分類区分ごとの判断基準や、素材・大きさによる分岐、排出方法などのルール。判定の根拠として使う。

### `*.csv.metadata.json`（旧CSV取り込み方式の補助情報）
CSVを直接Knowledge Baseへ取り込む方式を試した際のサイドカー。現在のAWS本番では、
`infra/scripts/build_knowledge_records.py`がCSVを1品目1テキスト文書へ変換し、
`infra/generated/knowledge_records/`から取り込むため、実行時には使用しない。

### `item_embeddings.npz`（生成物）
`items.csv` を事前Embeddingしたベクトル索引。LambdaからTitan Embed Textを直接呼べる環境、
またはローカル比較実験で使用する。現在のAWS本番の意味検索はManaged Knowledge Baseが担当する。

### `<地区>/calendar/<年>.csv`（収集日を出す場合に必要）
地区ごとの収集カレンダー。次回収集日の算出に使う。地区単位で分ける。

## 新しい自治体・地区を追加する手順

1. `data/regions/<自治体>/common/knowledge/` を作り、`items.csv`（＋ルールCSV）を配置する。
2. 区分体系が9区分と異なる場合、`CATEGORY_NAMES` を更新する。
3. `infra/scripts/build_knowledge_records.py`で1品目1文書へ変換し、Knowledge Baseへ同期する。
4. 自前Embeddingを利用する環境では、追加で品目Embedding索引を生成する。
   ```bash
   cd backend
   uv run python build_item_embeddings.py \
     --source ../data/regions/<自治体>/common/knowledge/items.csv \
     --output ../data/regions/<自治体>/common/knowledge/item_embeddings.npz
   ```
5. 収集日を出す場合は `<自治体>/<地区>/calendar/<年>.csv` を配置する。
6. デプロイ時は `scripts/package_backend.sh` が参照するパスに合わせて同梱する。

## 出典・二次利用の注意

分別データは各自治体の公開資料に基づく。二次利用条件は自治体ごとに異なるため、
取り込み元の規約を確認し、追跡・再配布の要否に従うこと。
