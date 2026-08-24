# ごみ分別AIあいまい検索

松山市・清水地区を対象に、名前が分からないごみも自然な言葉から検索できるFlutterアプリです。

地域資料をRAGで検索し、分類・出し方・次回収集日を回答します。判定に必要な情報が足りない場合は、素材などを確認する追加質問を返します。

## 使い方

Flutter SDKとChromeがあれば利用できます。AWS認証やローカルBackendの起動は不要です。

`frontend/` ディレクトリで次を実行してください。

```bash
flutter pub get
flutter run -d chrome \
  --dart-define=API_BASE_URL=https://620bktqeq9.execute-api.ap-northeast-1.amazonaws.com
```

初期画面ではログインをスキップして利用できます。

## 主な機能

- 曖昧な表現からのごみ分類
- 松山市の地域資料を使ったRAG検索
- 判定に必要な追加質問
- 清水地区の次回収集日の表示
- 検索結果・確信度などのログ分析

## 構成

| パス | 内容 |
| --- | --- |
| `frontend/` | Flutterアプリ |
| `backend/` | FastAPI、RAG検索、分類処理 |
| `data/` | 松山市の分別資料と清水地区の収集カレンダー |
| `infra/` | TerraformとAWS構成 |
| `scripts/` | AWSの構築・削除・デプロイスクリプト |

## AWS環境の管理

```bash
# 構築・更新
./scripts/aws-up.sh

# 削除
./scripts/aws-down.sh
```

AWS構成、費用、権限、ローカルBackendの起動方法は [`infra/README.md`](infra/README.md) を参照してください。

プロンプトと分類処理は `backend/app/services/waste_guide_service.py`、モデルや検索件数などの設定は `backend/app/config.py` にあります。
