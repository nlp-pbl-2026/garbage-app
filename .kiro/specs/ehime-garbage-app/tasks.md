# Implementation Plan: 愛媛県ゴミ出しアプリ

## Overview

Flutter（Dart）を使用した愛媛県向けゴミ出しアプリのプロトタイプ実装。Riverpodによる状態管理、ローカルJSONデータソース、table_calendarによるカレンダー表示を中心に段階的に構築する。データモデル→サービス層→プロバイダー→UI画面の順で実装し、各段階でテストを挟む。

## Tasks

- [x] 1. プロジェクト構造のセットアップとデータモデル定義
  - [x] 1.1 Flutterプロジェクト初期化と依存パッケージ追加
    - `flutter create` でプロジェクト作成（既存プロジェクトがない場合）
    - `pubspec.yaml` に以下を追加: `flutter_riverpod`, `table_calendar`, `shared_preferences`, `glados`（dev）
    - `assets/data/` ディレクトリ構造を作成
    - `lib/` 配下のディレクトリ構成を設計書に従い作成（models, providers, services, screens, widgets, constants, utils）
    - _Requirements: 全体_

  - [x] 1.2 ローカルJSONデータファイルの作成
    - `assets/data/prefectures.json` を作成（愛媛県データ）
    - `assets/data/municipalities.json` を作成（松山市、今治市等）
    - `assets/data/districts.json` を作成（各市区町村の地区データ）
    - `assets/data/garbage_items.json` を作成（ゴミ品目データ）
    - `assets/data/collection_schedules.json` を作成（収集ルールデータ）
    - `assets/data/popular_items.json` を作成（よく検索される品目）
    - `pubspec.yaml` の `assets` セクションに上記ファイルを登録
    - _Requirements: 1.2, 1.3, 2.2, 3.1, 5.1_

  - [x] 1.3 定数ファイルと色定義の作成
    - `lib/constants/colors.dart` にGarbage_Category色定義を実装
    - `lib/constants/strings.dart` にアプリ内文字列定数を定義
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

  - [x] 1.4 データモデルクラスの実装
    - `lib/models/region.dart`: Prefecture, Municipality, District, RegionSetting クラス
    - `lib/models/garbage_item.dart`: GarbageCategory enum, GarbageItem クラス
    - `lib/models/garbage_category.dart`: CategoryColors クラス（色・ラベルマッピング）
    - `lib/models/collection_schedule.dart`: ScheduleEntry, CollectionRule クラス
    - 各モデルに `fromJson` / `toJson` メソッドを実装
    - RegionSetting に `displayName` ゲッターを実装（20文字制限付き）
    - CollectionRule に `generateDatesForMonth` メソッドを実装
    - _Requirements: 1.4, 2.4, 5.1, 8.1, 8.2_

  - [ ]* 1.5 データモデルのプロパティテスト（Property 6, 7, 8）
    - **Property 6: 複数カテゴリ判定の正確性** - GarbageItemのhasMultipleCategoriesプロパティが正しく動作することを検証
    - **Validates: Requirements 2.5**
    - **Property 7: displayName生成の正確性** - RegionSettingのdisplayNameが20文字制限と省略記号ルールに従うことを検証
    - **Validates: Requirements 8.1, 8.2**
    - **Property 8: スケジュール日付生成の正確性** - CollectionRuleのgenerateDatesForMonthが正しい曜日・週に属する日付を生成することを検証
    - **Validates: Requirements 5.1**

  - [ ]* 1.6 データモデルのユニットテスト
    - Prefecture, Municipality, District の fromJson/toJson テスト
    - GarbageItem の fromJson テスト
    - CollectionRule の generateDatesForMonth 境界値テスト（月末、うるう年等）
    - _Requirements: 1.2, 1.3, 5.1_

- [ ] 2. サービス層の実装
  - [x] 2.1 RegionServiceの実装
    - `lib/services/region_service.dart` を作成
    - JSONファイルからの都道府県・市区町村・地区データの読み込みロジック
    - SharedPreferencesを使用した地域設定の保存・読み込みロジック
    - 階層フィルタリング（都道府県→市区町村→地区）の実装
    - _Requirements: 1.2, 1.3, 1.4, 1.7_

  - [ ]* 2.2 RegionServiceのプロパティテスト（Property 1, 2, 3）
    - **Property 1: 階層フィルタリングの正確性** - フィルタした結果のすべてのエントリが正しい親IDを持つことを検証
    - **Validates: Requirements 1.2, 1.3**
    - **Property 2: 地域設定のラウンドトリップ** - 保存→読み込みで元のRegionSettingと等価なオブジェクトが得られることを検証
    - **Validates: Requirements 1.4**
    - **Property 3: 地域選択バリデーション** - 3フィールドの組み合わせに対するバリデーション結果の正確性を検証
    - **Validates: Requirements 1.5**

  - [x] 2.3 GarbageServiceの実装
    - `lib/services/garbage_service.dart` を作成
    - キーワード検索ロジック（2文字以上、最大50件、部分一致）
    - よく検索される品目の取得ロジック（5-10件）
    - 品目IDによる詳細取得ロジック
    - 検索入力のバリデーション（2文字未満→空リスト、50文字超→切り詰め）
    - _Requirements: 2.1, 2.2, 2.6, 2.7, 3.1_

  - [ ]* 2.4 GarbageServiceのプロパティテスト（Property 4, 5）
    - **Property 4: 検索入力バリデーション** - 2文字未満で空リスト、50文字超で切り詰め後に検索実行されることを検証
    - **Validates: Requirements 2.1, 2.7**
    - **Property 5: 検索結果の正確性** - 結果が50件以下かつ各結果にクエリ文字列が部分一致として含まれることを検証
    - **Validates: Requirements 2.2**

  - [x] 2.5 ScheduleServiceの実装
    - `lib/services/schedule_service.dart` を作成
    - 月間収集スケジュールの生成ロジック（CollectionRuleからスケジュールエントリを生成）
    - 日付によるスケジュールフィルタリング
    - 次回収集日の計算ロジック
    - _Requirements: 5.1, 5.3, 5.4_

  - [ ]* 2.6 ScheduleServiceのプロパティテスト（Property 9, 10）
    - **Property 9: 日付→スケジュール検索の正確性** - 指定日付でフィルタした結果にはその日付と一致するエントリのみが含まれることを検証
    - **Validates: Requirements 5.3**
    - **Property 10: 次回収集日計算の正確性** - 次回収集日が基準日以降で最も近い日付であることを検証
    - **Validates: Requirements 5.4**

  - [x] 2.7 NotificationService（モック実装）の作成
    - `lib/services/notification_service.dart` を作成
    - リマインダー有効化/無効化のモック実装（SharedPreferencesでフラグ管理）
    - リマインダー状態の取得
    - プロトタイプ段階のため実際の通知配信はログ出力のみ
    - _Requirements: 6.4, 6.5, 6.6_

  - [x] 2.8 テキストユーティリティとキャッシュ判定の実装
    - `lib/utils/text_utils.dart` を作成
    - キャッシュ経過日数判定ロジックの実装（30日以上で古いデータ判定）
    - _Requirements: 10.6_

  - [ ]* 2.9 テキストユーティリティのプロパティテスト（Property 13）
    - **Property 13: キャッシュ経過日数判定** - 差分が30日以上でtrue、30日未満でfalseを返すことを検証
    - **Validates: Requirements 10.6**

- [x] 3. チェックポイント - モデルとサービス層の確認
  - すべてのテストが通ることを確認し、問題があればユーザーに質問する。

- [ ] 4. 状態管理層（Riverpod Provider）の実装
  - [x] 4.1 RegionProviderの実装
    - `lib/providers/region_provider.dart` を作成
    - `regionServiceProvider`: RegionServiceのプロバイダー
    - `regionSettingProvider`: StateNotifierProviderによる地域設定管理
    - RegionSettingNotifier: 地域設定の読み込み・保存・バリデーションを管理
    - _Requirements: 1.4, 1.5, 1.7_

  - [x] 4.2 SearchProviderの実装
    - `lib/providers/search_provider.dart` を作成
    - `garbageServiceProvider`: GarbageServiceのプロバイダー
    - `searchQueryProvider`: 検索クエリのStateProvider
    - `searchResultsProvider`: 検索結果のFutureProvider.autoDispose
    - `popularItemsProvider`: よく検索される品目のFutureProvider
    - _Requirements: 2.1, 2.2, 2.7, 3.1_

  - [x] 4.3 CalendarProviderの実装
    - `lib/providers/calendar_provider.dart` を作成
    - `scheduleServiceProvider`: ScheduleServiceのプロバイダー
    - `selectedDayProvider`: 選択日のStateProvider
    - `monthlyScheduleProvider`: 月間スケジュールのFutureProvider.family
    - `nextCollectionProvider`: 次回収集予定のFutureProvider
    - _Requirements: 5.1, 5.3, 5.4, 5.5_

  - [x] 4.4 SettingsProviderの実装
    - `lib/providers/settings_provider.dart` を作成
    - `notificationServiceProvider`: NotificationServiceのプロバイダー
    - `reminderEnabledProvider`: リマインダー状態のStateNotifierProvider
    - _Requirements: 6.4, 6.5, 6.6_

  - [ ]* 4.5 プロバイダーのユニットテスト
    - RegionSettingNotifierの状態遷移テスト
    - searchResultsProviderの検索実行テスト
    - monthlyScheduleProviderのデータ取得テスト
    - _Requirements: 1.4, 2.2, 5.1_

- [x] 5. UI画面の実装（ナビゲーションとメインフレーム）
  - [x] 5.1 アプリのエントリーポイントとナビゲーション実装
    - `lib/main.dart`: ProviderScopeでのアプリ初期化
    - `lib/app.dart`: MaterialApp設定、テーマ設定
    - BottomNavigationBar（検索・カレンダー・設定の3タブ）の実装
    - 初回起動判定ロジック（地域設定有無で遷移先を分岐）
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 1.1, 1.7_

  - [x] 5.2 地域ヘッダーウィジェットの実装
    - `lib/widgets/region_header.dart` を作成
    - 位置アイコン + 市区町村名・地区名の表示（20文字制限）
    - 編集アイコン押下で設定画面へ遷移
    - 地域未設定時のメッセージ表示
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 5.3 カテゴリタグウィジェットの実装
    - `lib/widgets/category_tag.dart` を作成
    - 色付きタグの表示（色 + テキストラベル）
    - 危険ごみの場合は警告アイコンを併記
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 5.4 カテゴリ表示のプロパティテスト（Property 11）
    - **Property 11: カテゴリ表示情報の一貫性** - 同一カテゴリに対して常に同一の色とラベルが返されることを検証
    - **Validates: Requirements 2.4, 9.1, 9.4, 9.5**

- [x] 6. UI画面の実装（地域選択）
  - [x] 6.1 地域選択画面の実装
    - `lib/screens/region_selection_screen.dart` を作成
    - 3段階ステッパー形式（都道府県→市区町村→地区）のUI
    - 各ステップでのリスト表示と選択処理
    - 「この地域で始める」ボタンと完了処理
    - 戻るボタンによる上位階層への遷移と選択状態リセット
    - 未選択時のバリデーションエラー表示
    - データ取得失敗時のエラーメッセージと再試行ボタン
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8_

  - [ ]* 6.2 地域選択画面のウィジェットテスト
    - 初回起動時に地域選択画面が表示されることを確認
    - ステップ遷移の動作確認
    - バリデーションエラー表示の確認
    - _Requirements: 1.1, 1.5_

- [x] 7. UI画面の実装（検索と品目詳細）
  - [x] 7.1 検索画面の実装
    - `lib/screens/search_screen.dart` を作成
    - 検索テキストフィールド（最大50文字）
    - 検索結果リスト表示（品目名 + カテゴリ色タグ）
    - 複数品目該当時のメッセージ表示
    - 検索結果なし時のメッセージ表示
    - 2文字未満時は検索非実行
    - `lib/widgets/search_result_tile.dart`: 検索結果1件の表示ウィジェット
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 7.2 よく検索される品目セクションの実装
    - `lib/widgets/popular_items_section.dart` を作成
    - タグ形式での品目表示（5-10件）
    - タグ選択時に該当品目の検索実行
    - データ取得失敗時はセクション非表示
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 7.3 品目詳細画面の実装
    - `lib/screens/item_detail_screen.dart` を作成
    - 品目名、カテゴリタグ、次回収集日、出し方説明の表示
    - 注意事項の条件付き表示（赤色注意ボックス）
    - 「カレンダーに登録」ボタン（プロトタイプではモック動作）
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 7.4 品目詳細画面のプロパティテスト（Property 12）
    - **Property 12: 注意事項の条件付き表示判定** - cautionフィールドがnon-null/非空の場合のみ注意表示フラグがtrueとなることを検証
    - **Validates: Requirements 4.3**

- [x] 8. チェックポイント - 検索機能の確認
  - すべてのテストが通ることを確認し、問題があればユーザーに質問する。

- [x] 9. UI画面の実装（カレンダーと設定）
  - [x] 9.1 カレンダー画面の実装
    - `lib/screens/calendar_screen.dart` を作成
    - table_calendarを使用した月間カレンダー表示
    - 各日付にカテゴリ色ドットインジケーター表示（最大5個）
    - カレンダー下部に色凡例を表示
    - 日付選択時に当日の収集予定一覧を表示
    - 収集予定なし日付選択時のメッセージ表示
    - 上部バナーに次回収集予定を表示
    - 月切り替え機能
    - `lib/widgets/calendar_day_marker.dart`: 日付マーカーウィジェット
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 9.2 設定画面の実装
    - `lib/screens/settings_screen.dart` を作成
    - 現在の地域情報表示（都道府県・市区町村・地区）
    - 地域変更ボタン→地域選択画面への遷移
    - 地域変更成功時のフィードバック表示（2秒間）
    - 保存失敗時のエラーメッセージと変更前データ保持
    - リマインダー通知トグル表示
    - リマインダー有効/無効の切り替え処理
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 9.3 カレンダー画面・設定画面のウィジェットテスト
    - カレンダーの月切り替え動作確認
    - 日付選択時の予定表示確認
    - 設定画面のトグル動作確認
    - _Requirements: 5.3, 5.5, 6.4_

- [x] 10. オフライン対応とエラーハンドリングの統合
  - [x] 10.1 オフラインデータキャッシュの実装
    - プロトタイプ段階ではローカルJSONがデフォルトデータソースのため、キャッシュ日時管理のみ実装
    - SharedPreferencesに最終更新日時を保存
    - 30日経過判定によるデータ古い通知の表示ロジック
    - _Requirements: 10.1, 10.2, 10.5, 10.6_

  - [x] 10.2 エラーハンドリングの統合
    - AsyncValueパターンによる統一的なローディング/エラー/データ表示
    - 各画面にエラー時の再試行ボタンを配置
    - JSONデータ読み込みエラー時のフォールバック処理
    - _Requirements: 1.6, 10.4, 10.5_

- [x] 11. 最終チェックポイント - 全体統合確認
  - すべてのテストが通ることを確認し、問題があればユーザーに質問する。

## Notes

- タスクに `*` が付いているサブタスクはオプションであり、MVP優先時にはスキップ可能
- 各タスクは要件への参照を含み、トレーサビリティを確保
- チェックポイントでは段階的に動作検証を行う
- プロパティテストはgladosライブラリを使用しコードの正しさを形式的に検証
- ユニットテスト・ウィジェットテストはflutter_testを使用
- 通知機能はプロトタイプ段階のためモック実装とする
- オフライン対応はローカルJSONのため基本的にオフライン動作だが、キャッシュ日時管理のみ実装

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4"] },
    { "id": 3, "tasks": ["1.5", "1.6"] },
    { "id": 4, "tasks": ["2.1", "2.3", "2.5", "2.7", "2.8"] },
    { "id": 5, "tasks": ["2.2", "2.4", "2.6", "2.9"] },
    { "id": 6, "tasks": ["4.1", "4.2", "4.3", "4.4"] },
    { "id": 7, "tasks": ["4.5"] },
    { "id": 8, "tasks": ["5.1", "5.2", "5.3"] },
    { "id": 9, "tasks": ["5.4", "6.1"] },
    { "id": 10, "tasks": ["6.2", "7.1", "7.2"] },
    { "id": 11, "tasks": ["7.3"] },
    { "id": 12, "tasks": ["7.4", "9.1", "9.2"] },
    { "id": 13, "tasks": ["9.3", "10.1", "10.2"] }
  ]
}
```
