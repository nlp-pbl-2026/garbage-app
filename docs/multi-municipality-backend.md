# 複数自治体バックエンドのデータ契約

標準の `data/regions/catalog.json` に登録している実自治体は松山市と八幡浜市です。八幡浜市の対応範囲は[データガイド](yawatahama-data.md)を参照してください。
バックエンドは登録された自治体の台帳・分類・品目CSV・NPZ索引・実日付カレンダーを
切り替えられます。Flutterも同じ台帳から生成したオフラインカタログで自治体を切り替えます
（[Flutterのデータ契約](multi-municipality-flutter.md)）。新しい自治体の公式データ整備と
曜日規則の日付展開は別の作業です。テスト用の架空自治体は本番カタログに登録しません。

## 読み込みの入口

`catalog.json` の `municipalities` に自治体IDと台帳の相対パスを登録します。
台帳は自治体ごとのディレクトリに置きます。自治体ごとにカレンダーや品目を検索し、
未登録の自治体、未知の地区、データ欠損時に他自治体のデータを代用しません。

```json
{
  "schema_version": 1,
  "municipalities": [
    {"id": "38201", "registry_path": "matsuyama/registry.json"}
  ]
}
```

`MUNICIPALITY_CATALOG_PATH` で別のカタログを指定できます。読み込み結果はプロセス内で
キャッシュされるため、配置や設定を変えた後はバックエンドを再起動します。
既存の `REGION_REGISTRY_PATH`、`KNOWLEDGE_ITEMS_PATH`、`EMBEDDING_INDEX_PATH`、
`CALENDAR_BUNDLE_PATH` は松山市専用の互換設定として維持します。
新自治体には、これらの松山市用環境変数を適用しません。

## 新自治体の台帳

次は形式を示す架空の例です。分類や日付の公式根拠には使用できません。
`collection_areas`、`calendars`、`legacy_district_candidates` は松山市と同じ構造です。
新自治体には `rule_profiles` を明示し、旧松山市形式からの暗黙の補完を行いません。

```json
{
  "municipality_id": "90001",
  "municipality_name": "試験市",
  "version": "test-2026.1",
  "valid_from": "2026-01-01",
  "valid_to": "2026-12-31",
  "collection_areas": [
    {"id": "90001-a", "name": "地区A", "calendar_id": "a", "rule_profile_id": "standard"}
  ],
  "calendars": [{"id": "a", "rule_profile_id": "standard"}],
  "rule_profiles": {
    "standard": {
      "items_path": "knowledge/items.csv",
      "embedding_index_path": "knowledge/item_embeddings.npz",
      "calendar_path": "generated/calendar-2026.json",
      "classification_rules": "この自治体の公式資料で確認した共通ルール・例外を記載する。",
      "size_question": "この自治体の指定袋に入る大きさですか？",
      "knowledge_title": "試験市ごみ分別資料",
      "categories": {
        "burn": {"name": "燃やすごみ", "collection_type_id": "burn", "cutoff": "08:30"},
        "carry": {"name": "持込対象", "answer_note": "公式案内に従って搬入してください。"}
      }
    }
  }
}
```

- `collection_areas` に任意の `display_name` を指定すると、検索文脈・回答の地区名に使います。省略時は従来の `name` を使い、地区ID・カレンダーの対応は変わりません。
- データパスは台帳のあるディレクトリを基準とし、その内部のファイルを参照します。
- 分類コードは分別設定内の文字列です。松山市の「可燃」「金・ガ」等への変換は不要です。
- 定期収集する分類は `collection_type_id` と `cutoff`（`HH:MM`）を指定します。
  同じ収集区分を複数の分類から参照できます。
- 定期収集しない分類には `collection_type_id` を指定せず、必要に応じて
  `answer_note` に申込・持込等の案内を記載します。粗大ごみという名称だけで
  戸別収集や定期収集を決めません。
- `classification_rules` は必須の文字列です。分類根拠が品目の注記ですべて表現できる
  場合は空文字も指定できます。公式資料から確認した内容だけを配置します。
- `valid_from` / `valid_to` は暦年・年度のどちらも表せます。期間外の日付は返しません。

松山市の既存台帳と生成物は変更せず、互換アダプターが従来の分類・パス・搬出期限を
補います。中島の79行と1,756品目の候補索引の共有処理、缶・びんの追加質問は松山市の
中島プロファイルに限定します。他市町で同じプロファイル名を付けても適用しません。

## 品目・索引・検索

CSVは既存の `item_id,item,category,category_display,note` を基本とし、必要に応じて
`reading,search_text` を追加できます。`disposal_instructions` は区分共通の出し方を回答根拠に追加する任意列で、Embeddingテキストには含めません。
条件付き分類には `category_options`（分類コード配列のJSON文字列）を任意で指定できます。
これは注記の条件を満たしたときの候補であり、自動的な分類確定ではありません。松山市の従来の根拠チェックは変更しません。NPZは `vectors,item_ids,model_id,dimensions` を
保持します。`items.csv` の隣に `index_manifest.json` が必要です。

```json
{
  "municipality_id": "90001",
  "profile_id": "standard",
  "source_sha256": "CSVファイルのSHA-256",
  "index_sha256": "NPZファイルのSHA-256",
  "item_count": 100,
  "model_id": "amazon.titan-embed-text-v2:0",
  "dimensions": 1024
}
```

実際のハッシュ・件数・モデル・次元を記録してください。索引のIDとCSVのID、配列形状も
実行時に検査します。自治体内で候補索引を共用する場合は各プロファイルの
`index_profile_id` に共通索引のプロファイルIDを指定します。これは公式に確認した
範囲の候補取得の共有であり、他地域の分類・注記を流用する許可ではありません。
既存松山市索引には生成時の自治体IDがないため、従来のマニフェストを互換扱いします。

Nova Liteによる言い換え・判定、TitanによるクエリEmbedding、上位候補数・しきい値は
従来どおりです。既定の `USE_BEDROCK_KNOWLEDGE_BASE=false`、
`LEXICAL_SEARCH_ENABLED=false` も変更しません。比較用のManaged Knowledge Baseを
新自治体で利用する場合は、そのプロファイルに専用の `knowledge_base_id` が必要です。
松山市のグローバルなKB設定には戻りません。

新自治体の検索根拠URIは `regional://自治体ID/分別設定ID/データ版/...` です。
`decide` は別自治体・別設定・別版の根拠を拒否します。松山市の既存
`local://items/...` と `nakajima://...` はFlutterとの互換性のため維持します。
この照合は地域の混在防止であり、クライアントが送る根拠本文の改変を認証する仕組みではありません。

## カレンダーとAPI

カレンダーJSONは既存の `municipality_id,version,valid_from,valid_to,calendars` と
各カレンダーの `verification_status,days` を使います。
`days` の値は分類コードではなく `collection_type_id` の配列です。同日の複数区分を
保持できます。新自治体ではカレンダーの自治体IDも必ず照合します。

台帳・分類設定が壊れている場合、検索データや索引の検証に失敗した場合はAPIを503に
します。未対応地域は422（品目一覧の未登録自治体は従来どおり404）です。
カレンダーが不足・未検証なら分類結果は返せますが、`next_collection` は `null` とし、
確認できないことを案内します。他地区の日付で埋めません。

検索APIのURLと既存JSON項目は維持しています。回答に任意の `collection_status` を追加し、収集日の未確認と今後の予定なしを区別します。省略時の地域は従来どおり松山市清水です。
新自治体では `municipality_id` と `district_id` を明示してください。
品目一覧の `category` にはその分別設定の分類コードを指定します。

### 収集区分単位の検証状態

一部の収集区分だけが未確認のカレンダーは `verification_status: partially_checked` にします。
`collection_type_verification` に、その分別設定の全 `collection_type_id` を記録してください。
各値は `{"status": "checked"}`、または `{"status": "unverified", "message": "確認が必要な内容", "source_url": "公式資料URL"}` です。
部分検証には確認済み・未確認の両方が必要です。未確認区分の日付を `days` に含めてはいけません。
バックエンドは不整合を拒否し、Flutterも未確認区分を通知・iCalへ流しません。
従来の `checked` カレンダーでこの項目を省略した場合は、既存どおり全区分を確認済みと扱います。

回答の `collection_status` は `status,message,source_url` を持ちます。
`unverified` は分類済みだが収集日未確認、`scheduled` は次回日付あり、
`no_upcoming_collection` は確認済み範囲に次回予定なし、`not_scheduled` は定期収集対象外です。
カレンダー欠損・版不一致は `missing_data` / `unverified_data` になります。
旧クライアントは追加項目を無視でき、従来の `next_collection` は維持します。

## パッケージと次の自治体追加

`scripts/package_backend.sh` は `package_backend_data.py` により、カタログに登録された
台帳と実行に必要なデータだけを同梱します。CSV・NPZのハッシュ・件数・識別情報、
カレンダーの検証状態を確認し、不足があれば停止します。原資料PDFやログは同梱しません。
原資料との公式照合はこの検査に加えて、自治体ごとに行ってください。

新しい自治体の追加では、公式資料取得、公式分類と収集区分の対応、条件付き品目、
地区・カレンダー対応を整備した後、専用索引とマニフェストを生成します。
その後にカタログへ登録し、公式資料の照合・検索評価・Flutter用データ生成と実機確認を実施します。
松山市の品目CSV・索引は再生成しません。
