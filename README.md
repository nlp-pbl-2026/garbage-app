# ごみサポ

名前が分からないごみも、自然な言葉や画像から分別区分を検索できるFlutterアプリです。

自治体の分別資料をTitan Embeddingによる意味検索で検索し、分類・出し方・次回収集日を回答します。判定に必要な情報が足りない場合は、素材などを確認する追加質問を返します。

現在は松山市の58収集地区に対応します。松山・北条地域と中島地域で分別設定を分け、2026年度の公式カレンダー43種類を共有原本から利用します（[データ配置ガイド](docs/data.md)）。

バックエンドとFlutterには、自治体別の台帳・分別設定・カレンダーを切り替える共通基盤があります。松山市に加え八幡浜市の2026年度公式データを追加しました（[対応範囲・未対応住所](docs/yawatahama-data.md)）。他市町の追加には専用の公式データ整備と検証が必要です（[Flutterの自治体データ契約](docs/multi-municipality-flutter.md)）。

清水地区を対象にした比較実験では、素のLLMやWeb検索付きLLMより高い精度と短い応答時間が得られました（[実験レポート](docs/experiments.md)）。この結果は全地区・中島地域での検索精度を示すものではありません。

> [!WARNING]
> 収集日は2026年度（2026年4月～2027年3月）の確認済みデータのみ表示します。別年度・未対応自治体には適用しません。中島地域では、根拠や条件が足りない品目の分類は確定せず、追加質問または判定保留にします。

## 使い方

対応済みのAPIへ接続する場合、Flutter側にはAWS認証やローカルBackendの起動は不要です。新規cloneではGit管理外のカレンダーを生成してから起動してください。[セットアップ手順](docs/yawatahama-data.md#新規cloneからの取得再生成)に、松山市・八幡浜市のデータ生成と、ローカルBackendも使う場合の索引配置・起動方法をまとめています。

ハッカソン審査用には、審査担当者から共有されたAPI URLを環境変数に設定し、
プロジェクトルートから次を実行してください。ヘルスチェック、Flutter依存関係の
取得、Chromeでの起動をまとめて実行します。

```bash
export GARBAGE_API_BASE_URL='https://<shared-api-endpoint>'
./scripts/run-demo.sh
```

接続先やデバイスを変える場合は、`GARBAGE_API_BASE_URL`、
`GARBAGE_FLUTTER_DEVICE`を指定できます。
APIの疎通だけを確認する場合は`./scripts/run-demo.sh --check`を使います。

個別に起動する場合は、`frontend/` ディレクトリで次を実行してください。

```bash
export GARBAGE_API_BASE_URL='https://<shared-api-endpoint>'
flutter pub get
flutter run -d chrome \
  --dart-define=API_BASE_URL="${GARBAGE_API_BASE_URL}"
```

初期画面ではログインをスキップして利用できます。

## 主な機能

- 曖昧な表現からのごみ分類
- テキストのみ・画像のみ・画像とテキストを組み合わせた検索
- 対象地域の分別資料を使ったRAG検索
- 判定に必要な追加質問
- 地区ごとの次回収集日の表示
- 検索結果・確信度などのログ分析

## 検索の仕組み（あいまい検索）

品名が分からない曖昧な入力から正解へ到達するため、検索クエリをTitan Text Embeddings V2でベクトル化し、上位候補を判定LLMへ渡します。

1. **クエリ変換**: Amazon Nova Liteがテキストと任意の画像を読み取り、曖昧な入力を検索向けに言い換える。
2. **意味検索**: Titan Text Embeddings V2でクエリをベクトル化し、Lambda同梱の`item_embeddings.npz`から候補を検索する。
3. **判定**: Amazon Nova Liteが画像と検索候補から分類を判定し、必要なら追加質問を返す。

検索画像はJPEG・PNG・GIF・WebPのいずれか1枚、3MBまでです。画像は検索リクエスト内でNova Liteへ渡し、S3や検索ログには保存しません。

両地域で既存の1,756品目のEmbedding索引を検索候補の取得に使います。中島地域では公式カレンダーに明記された79行の分別例・説明を優先し、共通索引から得た候補には中島地域のルールを適用します。松山・北条地域の分類や注意書きをそのまま中島の回答根拠にはしません。候補に入ることと分類を確定できることは別です。既存のAWS環境は、別途更新するまで旧バージョンのままです。

判定は素材・大きさ・製品/容器包装の区別などの分類原則を踏まえ、必要な場合のみ追加質問を1つ返します（`waste_guide_service.py`）。

## 構成

| パス | 内容 |
| --- | --- |
| `frontend/` | Flutterアプリ |
| `backend/` | FastAPI、Titan Embedding検索、分類処理 |
| `backend/evaluation/` | あいまい検索の評価パイプライン（データ生成・採点・比較） |
| `data/` | 自治体ごとの分別資料と地区別の収集カレンダー（[配置ガイド](docs/data.md)） |
| `infra/` | TerraformとAWS構成 |
| `scripts/` | AWSの構築・削除・デプロイスクリプト |
| `docs/` | データ配置ガイド・実験レポートなどのドキュメント |

自治体の分別資料から作成したCSVと生成カレンダーはGitに含めていません。松山市の既存Embedding索引は追跡し、八幡浜市の新規索引はGit管理外で取得・生成します。バックエンドの再構築・再デプロイや精度評価を行う場合は、[`docs/data.md`](docs/data.md)に従って必要なデータを取得・生成してください。

バックエンドの自治体別データ読み込み形式は[複数自治体バックエンドのデータ契約](docs/multi-municipality-backend.md)を参照してください。標準カタログには松山市と八幡浜市を登録しています。八幡浜市は20 PDFを22選択地区へ分け、紙類の曜日を確認できない1住所は除外しています。

## AWS環境の管理

審査用APIは認証不要ですが、API Gatewayで5 req/s、burst 10に制限しています。URLは審査関係者だけに共有し、FlutterへAWS認証情報や分析キーを埋め込まないでください。

```bash
# 構築・更新
./scripts/aws-up.sh

# 削除
./scripts/aws-down.sh
```

`aws-up.sh` はTerraformの適用と比較実験用Knowledge Baseの同期も行います。更新前にLambdaパッケージとTerraform planを確認してください。

AWS構成、費用、権限、ローカルBackendの起動方法は [`infra/README.md`](infra/README.md) を参照してください。

プロンプトと分類処理は `backend/app/services/waste_guide_service.py`、モデルや検索件数などの設定は `backend/app/config.py` にあります。

曖昧検索のデータセット生成と性能評価の手順は [`backend/evaluation/README.md`](backend/evaluation/README.md)、実験設定・結果・誤答分析は [`docs/experiments.md`](docs/experiments.md) を参照してください。
