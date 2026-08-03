# Implementation Plan: 通知カスタマイズ

## Overview

ゴミ種別（GarbageCategory）ごとに前日通知・当日通知のON/OFFを個別設定できる機能を実装する。データ層（NotificationCustomizationService）、状態管理層（NotificationCustomizationNotifier）、UI層（NotificationCustomizationWidget）の3層構成で、既存のNotificationServiceにフィルタリングロジックを統合する。

## Tasks

- [x] 1. データモデルとサービス層の実装
  - [x] 1.1 NotificationTimingType列挙型とCategoryNotificationSettingモデルを作成する
    - `lib/models/notification_timing_type.dart` に `NotificationTimingType` 列挙型（evening, morning）を定義する
    - `lib/models/category_notification_setting.dart` に `CategoryNotificationSetting` クラスを作成する
    - category, eveningEnabled, morningEnabled フィールドとcopyWithメソッドを実装する
    - _Requirements: 1.1_

  - [x] 1.2 NotificationCustomizationServiceを実装する
    - `lib/services/notification_customization_service.dart` を作成する
    - SharedPreferencesキー形式: `notification_category_{category}_{timing}`
    - `loadAllSettings()`: 全カテゴリの設定を読み込み、キー未存在時はデフォルトtrue
    - `saveSetting(category, timing, enabled)`: 指定カテゴリ・タイミングの設定を保存
    - `getEnabledCategories(timing)`: 指定タイミングで有効なカテゴリ一覧を返す
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.3 NotificationCustomizationServiceのプロパティテスト: 設定永続化ラウンドトリップ
    - **Property 1: 設定永続化ラウンドトリップ**
    - 任意のGarbageCategory × NotificationTimingType × bool値に対してsaveSetting→loadAllSettingsで同一値が返ること
    - **Validates: Requirements 1.2, 1.4, 1.5**

  - [ ]* 1.4 NotificationCustomizationServiceのプロパティテスト: 通知カテゴリフィルタリング
    - **Property 2: 通知カテゴリフィルタリング**
    - 任意のカテゴリ別ON/OFF設定パターンに対して、getEnabledCategories(timing)がONのカテゴリのみを返しOFFのカテゴリを含まないこと
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 2. 状態管理層の実装
  - [x] 2.1 NotificationCustomizationNotifierを実装する
    - `lib/providers/notification_customization_provider.dart` を作成する
    - `notificationCustomizationServiceProvider` でサービスのProviderを定義する
    - `notificationCustomizationProvider` でStateNotifierProviderを定義する
    - 初期化時にSharedPreferencesから設定を読み込みAsyncValue.loadingからAsyncValue.dataへ遷移する
    - `toggle(category, timing)` メソッドで設定トグルと永続化を実行する
    - トグル後にNotificationService.refreshNotifications()を呼び出して通知を再スケジュールする
    - エラー時はデフォルト全ON状態にフォールバックする
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 2.4_

  - [ ]* 2.2 NotificationCustomizationNotifierのユニットテスト
    - 初期化時にloading→data遷移すること
    - toggle操作後にsaveSettingとrefreshNotificationsが呼ばれること
    - SharedPreferences読み込み失敗時にエラー状態を公開しつつデフォルト全ONで動作すること
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. NotificationServiceへのフィルタリング統合
  - [x] 4.1 NotificationServiceのscheduleWeeklyNotificationsにカテゴリフィルタリングを追加する
    - `lib/services/notification_service.dart` の `scheduleWeeklyNotifications` メソッドを修正する
    - NotificationCustomizationServiceを利用して前日通知・当日通知それぞれの有効カテゴリを取得する
    - 前日通知: eveningEnabledカテゴリのみフィルタリングして通知スケジュール
    - 当日通知: morningEnabledカテゴリのみフィルタリングして通知スケジュール
    - フィルタリング後の有効カテゴリが空の場合はその通知をスキップする
    - 通知本文には有効カテゴリのラベルのみを結合して含める
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [ ]* 4.2 通知本文正確性のプロパティテスト
    - **Property 3: 通知本文の正確性**
    - 任意のカテゴリ別ON/OFF設定パターンに対して、生成される通知本文にONカテゴリのラベルのみが含まれOFFカテゴリのラベルが含まれないこと
    - **Validates: Requirements 2.5**

- [x] 5. UI層の実装
  - [x] 5.1 NotificationCustomizationWidgetを実装する
    - `lib/widgets/notification_customization_widget.dart` を作成する
    - ConsumerWidgetとして実装し、notificationCustomizationProviderをwatchする
    - reminderEnabledProviderを参照し、リマインダー無効時はSizedBox.shrink()を返す
    - 各GarbageCategory（5種別）に対してカテゴリカラー・ラベル付きの行を表示する
    - 各行に前日通知トグルと当日通知トグルを配置する
    - トグル操作時にnotifier.toggle()を呼び出す
    - AsyncValueのloading/error/data状態に応じたUI表示を実装する
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 5.2 設定画面にNotificationCustomizationWidgetを組み込む
    - `lib/screens/settings_screen.dart` の `_buildReminderCard` メソッド内に通知カスタマイズセクションを追加する
    - リマインダーONの場合に時刻ピッカーの下に種別カスタマイズウィジェットを表示する
    - 必要なimport文を追加する
    - _Requirements: 3.1, 3.5_

  - [ ]* 5.3 UIウィジェットテスト
    - リマインダーON時にカスタマイズセクションが表示されること
    - リマインダーOFF時にカスタマイズセクションが非表示であること
    - 5カテゴリ × 2トグルが表示されること
    - トグル操作後にUI状態が即座に更新されること
    - _Requirements: 3.1, 3.2, 3.4, 3.5_

- [x] 6. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- 既存のReminderNotifier・settingsProviderのパターンに従い一貫したコードスタイルを維持する
- SharedPreferencesのモック実装にはshared_preferences packageのsetMockInitialValuesを使用する

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "2.1"] },
    { "id": 3, "tasks": ["2.2", "4.1"] },
    { "id": 4, "tasks": ["4.2", "5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3"] }
  ]
}
```
