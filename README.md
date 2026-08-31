# あいまい検索が可能なゴミ分別アプリ

名前が分からないごみも、自然な言葉から分別区分を検索できるFlutterアプリです。

自治体の分別資料を**ハイブリッドRAG**（表層一致＋意味検索）で検索し、分類・出し方・次回収集日を回答します。判定に必要な情報が足りない場合は、素材などを確認する追加質問を返します。

自治体ごとのデータを差し替えることで対象地域を拡張できる設計で、現在は一例として **松山市清水地区** に対応しています（[データ配置ガイド](docs/data.md)）。

素のLLMやWeb検索付きLLMとの比較では、対象地域のデータに接地した本システムが最も高精度かつ高速でした（[実験レポート](docs/experiments.md)）。

> [!WARNING]
> 現在は、**愛媛県松山市清水地区** のみに対応しています。
> 他の地域・自治体に対応させる際は、そのデータを用意する必要があります。

## 使い方

Flutter SDKとChromeがあれば利用できます。AWS認証やローカルBackendの起動は不要です。

ハッカソン審査用には、プロジェクトルートから次を実行してください。公開APIの
ヘルスチェック、Flutter依存関係の取得、Chromeでの起動をまとめて実行します。

```bash
./scripts/run-demo.sh
```

接続先やデバイスを変える場合は、`GARBAGE_API_BASE_URL`、
`GARBAGE_FLUTTER_DEVICE`を指定できます。
APIの疎通だけを確認する場合は`./scripts/run-demo.sh --check`を使います。

個別に起動する場合は、`frontend/` ディレクトリで次を実行してください。

```bash
flutter pub get
flutter run -d chrome \
  --dart-define=API_BASE_URL=https://620bktqeq9.execute-api.ap-northeast-1.amazonaws.com
```

初期画面ではログインをスキップして利用できます。

## 主な機能

- 曖昧な表現からのごみ分類
- 対象地域の分別資料を使ったRAG検索
- 判定に必要な追加質問
- 地区ごとの次回収集日の表示
- 検索結果・確信度などのログ分析

## 検索の仕組み（あいまい検索）

品名が分からない曖昧な入力から正解へ到達するため、2種類の検索を統合（RRF）して上位候補を判定LLMへ渡します。

1. **表層一致検索** (`item_search_service.py`): 品目辞典 `items.csv` の各品目名に対する文字列（bigram）一致。正式名に近い入力に強い。
2. **意味検索**: AWS本番ではBedrock Managed Knowledge Baseから、1品目1文書で取り込んだ松山市資料を検索する。「プチプチ→エアキャップ」のような言い換えに強い。

AWS本番はLambdaのTitan直接呼び出し権限がないため、`USE_BEDROCK_KNOWLEDGE_BASE=true`でKnowledge Base経路を使用します。`embedding_search_service.py`と`build_item_embeddings.py`は、将来権限が得られた場合とローカル比較実験のために残しています。

判定は素材・大きさ・製品/容器包装の区別などの分類原則を踏まえ、必要な場合のみ追加質問を1つ返します（`waste_guide_service.py`）。

## 構成

| パス | 内容 |
| --- | --- |
| `frontend/` | Flutterアプリ |
| `backend/` | FastAPI、ハイブリッドRAG検索、分類処理 |
| `backend/evaluation/` | あいまい検索の評価パイプライン（データ生成・採点・比較） |
| `data/` | 自治体ごとの分別資料と地区別の収集カレンダー（[配置ガイド](docs/data.md)） |
| `infra/` | TerraformとAWS構成 |
| `scripts/` | AWSの構築・削除・デプロイスクリプト |
| `docs/` | データ配置ガイド・実験レポートなどのドキュメント |

## AWS環境の管理

審査用APIは認証不要ですが、API Gatewayで5 req/s、burst 10に制限しています。URLは審査関係者だけに共有し、FlutterへAWS認証情報や分析キーを埋め込まないでください。

```bash
# 構築・更新
./scripts/aws-up.sh

# 削除
./scripts/aws-down.sh
```

AWS構成、費用、権限、ローカルBackendの起動方法は [`infra/README.md`](infra/README.md) を参照してください。

プロンプトと分類処理は `backend/app/services/waste_guide_service.py`、モデルや検索件数などの設定は `backend/app/config.py` にあります。

曖昧検索のデータセット生成と性能評価の手順は [`backend/evaluation/README.md`](backend/evaluation/README.md)、実験設定・結果・誤答分析は [`docs/experiments.md`](docs/experiments.md) を参照してください。
