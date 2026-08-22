# Implementation Plan: 粗大ごみ申し込み連携

## Overview

粗大ごみ収集の情報提供・申し込みガイド機能を実装する。バックエンドにSQLAlchemy モデルとFastAPIエンドポイントを追加し、フロントエンドにRiverpod + Widgetベースの画面群、キャッシュ付きリポジトリ、ローカル状況追跡、通知スケジューリングを構築する。既存のメイン画面・検索機能との統合も含む。

## Tasks

- [x] 1. バックエンド: モデル・スキーマ・ルーター構築
  - [x] 1.1 SQLAlchemyモデルの追加 (MunicipalityConfig, BulkyWasteItem)
    - `backend/app/models.py` に `MunicipalityConfig` と `BulkyWasteItem` クラスを追加
    - `municipality_id` にユニーク制約、`BulkyWasteItem.municipality_id` にForeignKey設定
    - `steps` カラムはJSON型、`fee_amount` は Integer(0〜99999)
    - `item_name_kana` をソート用に追加、`garbage_item_name` を検索連携用に追加
    - _Requirements: 8.1, 8.2, 8.4_

  - [x] 1.2 Pydanticスキーマの追加
    - `backend/app/schemas.py` に `MunicipalityConfigResponse`, `ApplicationStep`, `BulkyWasteItemResponse`, `BulkyWasteItemListResponse` を追加
    - `fee_amount` に `ge=0, le=99999` バリデーション
    - `BulkyWasteItemListResponse` に `total_count` と `municipality_name` を含める
    - _Requirements: 8.4_

  - [x] 1.3 FastAPIルーターの作成
    - `backend/app/routers/bulky_waste_router.py` を新規作成
    - `GET /api/bulky-waste/config/{municipality_id}`: 自治体設定返却、404対応
    - `GET /api/bulky-waste/items/{municipality_id}`: 品目一覧返却、search/sort_by/sort_orderクエリパラメータ対応、最大500件
    - `GET /api/bulky-waste/items/{municipality_id}/{item_id}`: 品目詳細返却
    - _Requirements: 8.1, 8.2, 8.6_

  - [x] 1.4 ルーターをmain.pyに登録
    - `backend/app/main.py` で `bulky_waste_router` をインポートし `app.include_router` で登録
    - _Requirements: 8.1_

  - [ ]* 1.5 バックエンドAPIのユニットテスト
    - `pytest` + `httpx` で3エンドポイントの正常応答・404・パラメータバリデーションをテスト
    - _Requirements: 8.1, 8.2, 8.6_

  - [ ]* 1.6 Property 13のテスト: Fee response structure validation
    - **Property 13: Fee response structure validation**
    - Hypothesis を使い、任意の BulkyWasteItem レスポンスの `fee_amount` が [0, 99999] 範囲内の整数であること、通貨単位が "yen" であることを検証
    - **Validates: Requirements 8.4**

- [x] 2. Checkpoint - バックエンドのテスト確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. フロントエンド: モデル・リポジトリ・プロバイダー構築
  - [x] 3.1 Dartモデルクラスの作成
    - `frontend/lib/models/bulky_waste.dart` を新規作成
    - `MunicipalityConfig`, `ApplicationStep`, `BulkyWasteItem`, `ApplicationRecord` クラスとenums (`FeeStructureType`, `ApplicationMethod`, `ApplicationStatus`) を定義
    - 各クラスに `fromJson` / `toJson` メソッドを実装
    - `ApplicationRecord` に `id` (UUID), `itemName` (最大50文字), `collectionDate`, `status`, `createdAt`, `updatedAt` を含める
    - _Requirements: 2.2, 3.2, 7.1_

  - [x] 3.2 BulkyWasteRepositoryの作成
    - `frontend/lib/repositories/bulky_waste_repository.dart` を新規作成
    - `getMunicipalityConfig(municipalityId)`: API呼び出し → 成功時キャッシュ保存 → 失敗時キャッシュフォールバック
    - `getItems(municipalityId, {search, sortBy, sortOrder})`: 同様のAPI + キャッシュパターン
    - `getItemDetail(municipalityId, itemId)`: 品目詳細取得
    - 10秒タイムアウト設定、キャッシュにはSharedPreferencesを使用
    - キャッシュ使用時に `isStale` フラグを返す仕組みを実装
    - _Requirements: 8.3, 8.5, 8.7_

  - [x] 3.3 Riverpodプロバイダーの作成
    - `frontend/lib/providers/bulky_waste_provider.dart` を新規作成
    - `bulkyWasteRepositoryProvider`: リポジトリのシングルトン提供
    - `municipalityConfigProvider`: 地域設定に連動した `FutureProvider`
    - `bulkyWasteItemsProvider`: `FutureProvider.family` で検索・ソート対応
    - `applicationRecordsProvider`: `StateNotifierProvider` でローカル申し込み記録管理
    - _Requirements: 2.1, 2.4, 3.1_

  - [ ]* 3.4 モデル・リポジトリのユニットテスト
    - `fromJson` / `toJson` の往復一致テスト
    - キャッシュフォールバックロジックのテスト
    - _Requirements: 8.5_

- [x] 4. フロントエンド: 粗大ごみメイン画面とタブ構成
  - [x] 4.1 BulkyWasteScreenの作成
    - `frontend/lib/screens/bulky_waste_screen.dart` を新規作成
    - TabBar構成: 品目一覧 / 申し込みガイド / 状況追跡 の3タブ
    - `municipalityConfigProvider` を watch し、ローディング中はインジケーター表示
    - データ取得成功時: 自治体名・収集頻度・受付時間・収集ルールを概要セクションに表示
    - Municipality_Config未登録時: 「粗大ごみ情報は現在登録されていません」メッセージ表示
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [ ]* 4.2 Property 14のテスト: Municipality config display completeness
    - **Property 14: Municipality config display completeness**
    - glados を使い、任意の有効な `MunicipalityConfig` に対し画面概要に `municipalityName`, `collectionFrequency`, `receptionHours`, `collectionRules` が全て表示されることを検証
    - **Validates: Requirements 2.2**

- [x] 5. フロントエンド: 品目一覧・検索・ソート
  - [x] 5.1 ItemListViewウィジェットの作成
    - `frontend/lib/widgets/bulky_waste/item_list_view.dart` を新規作成
    - 品目一覧を `ListView.builder` で表示（品目名・カテゴリ・手数料「〇〇円」形式）
    - デフォルトソート: `item_name_kana` の五十音順
    - 検索テキストフィールド: 1文字以上入力で `item_name` / `category` の部分一致フィルタリング
    - ソート切替UI: 名前順 / 手数料昇順 / 手数料降順
    - 検索結果0件時: 「該当する品目が見つかりません」メッセージ表示
    - API失敗時: エラーメッセージ + リトライボタン表示
    - 品目タップで `FeeDisplayScreen` へ遷移
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 5.2 Property 1のテスト: Sort invariant
    - **Property 1: Sort invariant**
    - glados を使い、任意の品目リストとソートモードに対し、ソート後のリストが指定基準で正しく順序付けされていることを検証
    - **Validates: Requirements 3.1, 3.5**

  - [ ]* 5.3 Property 2のテスト: Search filter correctness
    - **Property 2: Search filter correctness**
    - glados を使い、任意のキーワードと品目リストに対し、フィルタ結果が `item_name` / `category` 部分一致の品目のみを含むことを検証
    - **Validates: Requirements 3.3**

  - [ ]* 5.4 Property 3のテスト: Item list rendering completeness
    - **Property 3: Item list rendering completeness**
    - glados を使い、任意の `BulkyWasteItem` のレンダリング出力に品目名・カテゴリ・手数料+"円" が含まれることを検証
    - **Validates: Requirements 3.2**

- [x] 6. フロントエンド: 手数料詳細画面
  - [x] 6.1 FeeDisplayScreenの作成
    - `frontend/lib/screens/fee_display_screen.dart` を新規作成
    - 品目名・サイズカテゴリ・手数料（整数 + "円"）・備考（最大200文字）を表示
    - `fee_structure_type` に応じた表示切替:
      - `size_based`: サイズ閾値(cm)と各段階の手数料
      - `weight_based`: 重量範囲(kg)と各段階の手数料
      - `fixed`: 単一の手数料金額
    - 該当ティアのハイライト表示
    - 手数料情報未登録時: 「手数料情報がありません」+ 自治体連絡先表示
    - 画面下部に `ExternalLinkHandler` を配置
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 6.2 Property 4のテスト: Fee display by structure type
    - **Property 4: Fee display by structure type**
    - glados を使い、任意の品目と `fee_structure_type` に対し、適切な手数料表示パターンが出力されることを検証
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

- [x] 7. フロントエンド: 申し込みガイド
  - [x] 7.1 ApplicationGuideViewの作成
    - `frontend/lib/widgets/bulky_waste/application_guide_view.dart` を新規作成
    - `MunicipalityConfig.steps` をステップ番号付きリストで表示（1〜N）
    - 標準5ステップ: 品目確認 → 手数料確認 → 申し込み → 処理券購入 → 排出
    - 各ステップの `title`, `description` を表示、`notes` がある場合はハイライトボックスで表示
    - 自治体固有の追加ステップも正しい順序で表示
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 7.2 Property 5のテスト: Application guide step rendering
    - **Property 5: Application guide step rendering**
    - glados を使い、N個のステップを持つ任意の `MunicipalityConfig` に対し、ガイドがN個のステップを1〜N番号で表示し、notes付きステップは distinct 表示されることを検証
    - **Validates: Requirements 5.1, 5.3, 5.4**

- [x] 8. フロントエンド: 外部窓口遷移
  - [x] 8.1 ExternalLinkHandlerの作成
    - `frontend/lib/widgets/bulky_waste/external_link_handler.dart` を新規作成
    - `application_method` に応じたボタン表示:
      - `web_form`: Webフォームボタンのみ
      - `phone`: 電話ボタンのみ
      - `both`: 両方表示
    - Webボタンタップ: `url_launcher` でデフォルトブラウザ起動
    - 電話ボタンタップ: 確認ダイアログ表示 → `url_launcher` で `tel:` スキーム起動
    - URL起動失敗時: エラーメッセージ + コピー可能URLテキスト表示
    - 電話起動失敗時: エラーメッセージ + コピー可能電話番号テキスト表示
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 8.2 Property 6のテスト: External link button visibility
    - **Property 6: External link button visibility**
    - glados を使い、任意の `application_method` に対し、表示されるボタンの組み合わせが正しいことを検証
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [x] 9. Checkpoint - 画面群のテスト確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. フロントエンド: 申し込み状況追跡
  - [x] 10.1 StatusTrackerViewの作成
    - `frontend/lib/widgets/bulky_waste/status_tracker_view.dart` を新規作成
    - 申し込み記録の作成フォーム: 品目名（最大50文字）・収集予定日（今日以降）・ステータス選択
    - バリデーション: 品目名空/空白のみ → エラー、過去日付 → エラー
    - アクティブ記録リスト: ステータスアイコン付き一覧表示
    - ステータス変更: `applied` / `ticketPurchased` / `awaitingCollection` を任意順序で変更可能
    - 完了マーク: `completed` 設定時にアーカイブリストへ移動
    - 期限超過: 収集日が過ぎた未完了レコードに「期限超過」表示
    - アーカイブセクション: 完了済み記録を別セクションでアクセス可能に
    - SharedPreferences で記録を永続化
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6, 7.7_

  - [x] 10.2 通知スケジューリングの実装
    - `flutter_local_notifications` で収集日24時間前にローカル通知をスケジュール
    - 記録作成時・収集日変更時に通知を再スケジュール
    - `completed` ステータスの記録は通知をキャンセル
    - _Requirements: 7.4_

  - [ ]* 10.3 Property 7のテスト: Application record creation validation
    - **Property 7: Application record creation validation**
    - glados を使い、任意の (itemName, collectionDate) ペアに対し、有効入力では記録が作成され、無効入力ではリストが不変であることを検証
    - **Validates: Requirements 7.1, 7.6**

  - [ ]* 10.4 Property 8のテスト: Status transition freedom
    - **Property 8: Status transition freedom**
    - glados を使い、任意の既存レコードと任意のターゲットステータスに対し、ステータス更新が常に成功することを検証
    - **Validates: Requirements 7.2, 7.3**

  - [ ]* 10.5 Property 9のテスト: Collection notification scheduling
    - **Property 9: Collection notification scheduling**
    - glados を使い、収集日が24時間以内かつ未完了の記録には通知スケジュールされ、それ以外には通知されないことを検証
    - **Validates: Requirements 7.4**

  - [ ]* 10.6 Property 10のテスト: Completed record archival
    - **Property 10: Completed record archival**
    - glados を使い、ステータスを `completed` に変更した記録がアクティブリストから消えアーカイブリストに現れることを検証
    - **Validates: Requirements 7.5**

  - [ ]* 10.7 Property 11のテスト: Overdue record indication
    - **Property 11: Overdue record indication**
    - glados を使い、収集日が過去で未完了の記録が「期限超過」とマークされることを検証
    - **Validates: Requirements 7.7**

- [x] 11. フロントエンド: ナビゲーション導線
  - [x] 11.1 MainScreenにFABを追加
    - `frontend/lib/screens/main_screen.dart` の `Scaffold` に `floatingActionButton` を追加
    - ラベル: "粗大ごみ"、アイコン: ゴミ関連アイコン
    - タップ時の分岐ロジック:
      - Region_Setting が null → RegionSelectionScreen へ遷移 + 「地域設定が必要です」メッセージ
      - Region_Setting 設定済み → BulkyWasteScreen へ遷移
    - 全タブから常時アクセス可能な位置に配置
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 11.2 ナビゲーション分岐のウィジェットテスト
    - Region null時とRegion設定済み時の遷移先を検証するwidget test
    - _Requirements: 1.3, 1.4_

- [x] 12. フロントエンド: 検索結果との連携
  - [x] 12.1 検索結果に粗大ごみリンクを追加
    - 既存の検索結果タイルを拡張
    - `GarbageItem.name` と `BulkyWasteItem.garbage_item_name` の文字列完全一致でマッピング判定
    - マッピングあり かつ Municipality_Config が存在する場合のみ粗大ごみリンク表示
    - リンクタップで `FeeDisplayScreen` へ品目IDとmunicipality_idを渡して遷移
    - データ取得失敗時: エラーメッセージ表示、検索結果画面に留まる
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 12.2 Property 12のテスト: Bulky waste link visibility in search results
    - **Property 12: Bulky waste link visibility in search results**
    - glados を使い、任意の GarbageItem と municipality に対し、リンク表示条件が正しく判定されることを検証
    - **Validates: Requirements 9.1, 9.4, 9.5**

- [x] 13. Final checkpoint - 全テスト確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (glados for Dart, Hypothesis for Python)
- Unit tests validate specific examples and edge cases
- `url_launcher` パッケージが `pubspec.yaml` に追加される必要あり（ExternalLinkHandler用）
- バックエンドの `hypothesis` パッケージが `requirements.txt` に追加される必要あり

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "3.1"] },
    { "id": 1, "tasks": ["1.3", "3.2", "3.3"] },
    { "id": 2, "tasks": ["1.4", "1.5", "1.6", "3.4"] },
    { "id": 3, "tasks": ["4.1", "5.1", "7.1", "8.1"] },
    { "id": 4, "tasks": ["4.2", "5.2", "5.3", "5.4", "6.1", "7.2", "8.2"] },
    { "id": 5, "tasks": ["6.2", "10.1", "10.2"] },
    { "id": 6, "tasks": ["10.3", "10.4", "10.5", "10.6", "10.7", "11.1"] },
    { "id": 7, "tasks": ["11.2", "12.1"] },
    { "id": 8, "tasks": ["12.2"] }
  ]
}
```
