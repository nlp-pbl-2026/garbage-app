# Implementation Plan: コア通知機能 (notification)

## Overview

既存の `NotificationService`（`frontend/lib/services/notification_service.dart`）を土台に、要件文書のすべての受け入れ基準を満たすよう形式化・堅牢化する。実装言語は既存コードに合わせて **Dart / Flutter** を使用する。

副作用（OS権限・通知プラグイン・SharedPreferences・現在時刻）を依存注入で差し替え可能にし、コアロジックをプロパティベーステスト（PBT, `glados`）で検証できる構造にする。各タスクは前のタスクの成果物の上に積み上げ、最後に UI・起動フロー・ナビゲーションへ配線する。

プロパティベーステストには `glados` を採用し、各プロパティテストは最低100回反復、対応する設計プロパティをコメントタグ（`// Feature: notification, Property {番号}: {本文}`）で明示する。

## Tasks

- [x] 1. 依存抽象化と結果型の土台を整備する
  - [x] 1.1 結果列挙型と依存インターフェースを定義する
    - `EnableResult`（success / permissionDenied / requestFailed）、`SaveTimeResult`（success / failed）、`PermissionOutcome`（granted / denied / requestError）を `NotificationService` と同一ファイルまたは近接ファイルに定義する
    - 注入可能なクロック `DateTime Function() now` を `NotificationService` のコンストラクタ引数として追加する
    - 通知プラグイン・権限リクエスタ・SharedPreferences アクセスを差し替え可能にするための内部フックを整理する（`_requestPermission()` / `_isPermissionGranted()` の private メソッドシグネチャを用意）
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 1.2 SharedPreferences 永続化スキーマのアクセサを実装する
    - キー `reminder_enabled` / `notification_district_id` / `notification_evening_hour` / `notification_evening_minute` / `notification_morning_hour` / `notification_morning_minute` の読み書きを実装する
    - 既定値（evening 20:00 / morning 06:00 / reminder_enabled=false）を適用する
    - 読み込み失敗時に `reminder_enabled=false` として動作するフォールバックを実装する
    - _Requirements: 4.1, 6.1, 6.5_

  - [ ]* 1.3 永続化の往復プロパティテストを書く
    - **Property 7: 通知設定の永続化は往復で保存される**
    - **Validates: Requirements 6.1, 6.2**
    - インメモリ SharedPreferences フェイクを使用

- [x] 2. 時刻管理（取得・保存・ロールバック）を実装する
  - [x] 2.1 通知時刻の取得・保存を実装する
    - `getEveningTime()` / `getMorningTime()` を実装し、`({int hour, int minute})` を返す
    - `setEveningTime(hour, minute)` / `setMorningTime(hour, minute)` で保存し、成功時のみ再スケジュールを呼ぶ
    - 保存失敗時は変更前の値へロールバックし `SaveTimeResult.failed` を返す
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.2 時刻往復のプロパティテストを書く
    - **Property 8: 通知時刻の設定は往復で保存される**
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 2.3 時刻保存失敗ロールバックのプロパティテストを書く
    - **Property 9: 時刻保存失敗時は変更前の値へロールバックする**
    - **Validates: Requirements 4.4**
    - 書き込み失敗を注入できる SharedPreferences ラッパを使用

  - [ ]* 2.4 既定時刻のユニットテストを書く
    - 時刻未設定時に evening 20:00 / morning 06:00 が返ることを検証
    - _Requirements: 4.1_

- [x] 3. Checkpoint - 永続化・時刻管理のテストが通ることを確認する
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. ScheduleWindow スケジューリング計算を実装する
  - [x] 4.1 ScheduleWindow 生成と収集日→通知の計算ロジックを実装する
    - 本日 00:00 起点の7日間 `[today, today+6]` を生成し、各日 `ScheduleService.getScheduleForDate(districtId, date)` を呼ぶ
    - `NotificationCustomizationService.getEnabledCategories(timing)` でタイミング別にカテゴリを絞り込む
    - EveningNotification（前日 + eveningTime、先頭日 i==0 は前日範囲外のため対象外）と MorningNotification（当日 + morningTime）を計算する
    - カテゴリ空の日はスキップ、配信時刻が現在時刻（注入クロック）以前の通知はスキップする
    - カテゴリラベルは `CategoryColors.getLabel(category)` で日本語化し `・` で連結、本文に含める。ラベル解決失敗時は当該タイミングの通知をスキップする（try/catch で保護）
    - 通知ペイロードに対象収集日の ISO8601 文字列を格納する
    - _Requirements: 1.2, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 4.2 scheduleWeeklyNotifications と cancelAll によるフル再構築を実装する
    - `cancelAll` 後に ScheduleWindow 内の通知を `zonedSchedule` で登録する（冪等なフル再構築）
    - タイムゾーンは既存どおり `timezone`（Asia/Tokyo）で初期化する
    - _Requirements: 1.2, 3.1, 3.2_

  - [ ]* 4.3 スケジュール対応性のプロパティテストを書く
    - **Property 3: スケジュールは対象地区の収集日に正確に対応する**
    - **Validates: Requirements 1.2, 3.1, 3.2, 3.6**

  - [ ]* 4.4 配信時刻が未来であることのプロパティテストを書く
    - **Property 4: スケジュールされる通知の配信時刻は常に現在時刻より後である**
    - **Validates: Requirements 3.5**

  - [ ]* 4.5 通知本文カテゴリラベルのプロパティテストを書く
    - **Property 5: 通知本文には対象日の有効カテゴリのラベルが含まれる**
    - **Validates: Requirements 3.3, 3.4**

- [x] 5. 有効化・無効化・再スケジュールの状態遷移を実装する
  - [x] 5.1 権限リクエストのラップを実装する
    - `_requestPermission()` を iOS/Android の `flutter_local_notifications` 権限API（`requestNotificationsPermission` 等）でラップし、`granted` / `denied` / `requestError` を返す
    - `_isPermissionGranted()` を実装する
    - _Requirements: 2.1_

  - [x] 5.2 enableReminder を実装する
    - `initialize()` → `_requestPermission()` を呼び、requestError / denied では flag=false のまま `requestFailed` / `permissionDenied` を返す
    - granted の場合のみ flag=true と districtId を保存し `scheduleWeeklyNotifications` を実行、`success` を返す
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4_

  - [x] 5.3 disableReminder と refreshNotifications を実装する
    - `disableReminder`: flag=false を保存し `cancelAll` を実行（配信処理中の通知は制御しない）
    - `refreshNotifications`: flag=true のときのみ現在設定（districtId・時刻・現在時刻・スケジュール）から全通知を再計算、flag=false では何もスケジュールしない
    - District_ID 変更時に `refreshNotifications` を呼ぶ導線を用意する
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 3.7, 4.5_

  - [ ]* 5.4 有効化成功のプロパティテストを書く
    - **Property 1: 有効化成功で状態が確定しスケジュールされる**
    - **Validates: Requirements 1.1, 1.2, 2.1, 2.3, 3.1, 3.2**

  - [ ]* 5.5 無効化のプロパティテストを書く
    - **Property 2: 無効化で全通知がキャンセルされフラグが false になる**
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 5.6 権限拒否・送信失敗での有効化中止のプロパティテストを書く
    - **Property 10: 権限が付与されない場合は有効化が中止される**
    - **Validates: Requirements 2.2, 2.4**

  - [ ]* 5.7 再スケジュールの冪等性プロパティテストを書く
    - **Property 6: 再スケジュールは現在設定のみに依存し冪等である**
    - **Validates: Requirements 3.7, 4.5, 6.3**

  - [ ]* 5.8 無効状態で新規通知をスケジュールしないプロパティテストを書く
    - **Property 11: 無効状態では新規通知をスケジュールしない**
    - **Validates: Requirements 1.5**

  - [ ]* 5.9 権限リクエスト発火のユニットテストを書く
    - 初回有効化時に権限リクエストが呼ばれることを検証
    - _Requirements: 2.1_

- [x] 6. Checkpoint - スケジューリングと状態遷移のテストが通ることを確認する
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. 起動時の復元処理を実装する
  - [x] 7.1 restoreOnStartup を実装する
    - SharedPreferences から設定を読み込み、読み込み失敗時は flag=false 相当として動作する
    - flag=true の場合 `scheduleWeeklyNotifications(districtId)` を実行、再スケジュール失敗時は例外を捕捉して flag=true を保持する
    - _Requirements: 6.2, 6.3, 6.4, 6.5_

  - [ ]* 7.2 起動時再スケジュール失敗のプロパティテストを書く
    - **Property 12: 起動時の再スケジュール失敗でもフラグは true を保持する**
    - **Validates: Requirements 6.4**

- [x] 8. 通知タップ時のナビゲーションを実装する
  - [x] 8.1 NotificationNavigationHandler を実装する
    - `GlobalKey<NavigatorState>` を保持し、`onNotificationResponse` でペイロード（ISO8601収集日）を解釈してカレンダー画面へ遷移する
    - `handleAppLaunchDetails()` で `getNotificationAppLaunchDetails()` を確認し、コールドスタート時は UI 準備後に遷移する
    - `navigateToCollectionDay(DateTime?)` でカレンダーの該当日を選択状態で開く
    - `NotificationService` の `onDidReceiveNotificationResponse` コールバックに接続する
    - _Requirements: 5.1, 5.2_

  - [ ]* 8.2 通知タップ遷移のウィジェット/統合テストを書く
    - フォアグラウンド/バックグラウンドからのタップでカレンダー画面へ遷移することを検証
    - コールドスタートからの遷移を検証
    - _Requirements: 5.1, 5.2_

- [x] 9. UI・状態管理・起動フローへ配線する
  - [x] 9.1 Riverpod Provider を実装/更新する
    - `NotificationService` をラップし、有効状態・時刻を UI に公開する Provider を既存 `settings_provider.dart` / `notification_customization_provider.dart` と同一パターンで実装する
    - _Requirements: 1.1, 1.3, 4.2, 4.3_

  - [x] 9.2 SettingsScreen に通知設定 UI を配線する
    - リマインダー ON/OFF トグルと通知時刻設定 UI を追加する
    - `enableReminder` の戻り値に応じて `permissionDenied` 時は OS設定画面への導線を含む案内、`requestFailed` 時は権限が必要な旨を提示する
    - `setEveningTime` / `setMorningTime` が `failed` を返した場合は保存失敗のエラーメッセージを表示する
    - _Requirements: 2.4, 2.5, 4.4_

  - [x] 9.3 起動フロー（main / app）へ配線する
    - `main()` で `initialize()` と `restoreOnStartup()` を起動時に呼ぶ
    - `MaterialApp.navigatorKey` に `NotificationNavigationHandler` の `GlobalKey<NavigatorState>` を接続し、UI 準備後に `handleAppLaunchDetails()` を呼ぶ
    - _Requirements: 5.1, 5.2, 6.2, 6.3_

  - [ ]* 9.4 権限拒否時の設定案内提示のユニット/ウィジェットテストを書く
    - 権限拒否状態で有効化を試行した際に OS設定画面への導線を含む案内が提示されることを検証
    - _Requirements: 2.5_

- [x] 10. Final checkpoint - すべてのテストが通ることを確認する
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- `*` が付いたサブタスクは任意（テスト）であり、MVP を急ぐ場合はスキップ可能。
- 各タスクはトレーサビリティのため具体的な要件番号を参照する。
- プロパティテストは Property 1〜12 を対象とし、各性質を単一のプロパティテストで実装する（`glados`、最低100回反復）。
- ユニット/ウィジェット/統合テストは、入力変化が乏しい受け入れ基準（2.1, 2.5, 4.1, 5.1, 5.2）を補完する。
- 副作用（通知プラグイン・権限・SharedPreferences・現在時刻）はフェイク/依存注入で差し替え、決定的に検証する。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "4.1", "5.1"] },
    { "id": 4, "tasks": ["4.2", "5.2"] },
    { "id": 5, "tasks": ["4.3", "4.4", "4.5", "5.3", "8.1"] },
    { "id": 6, "tasks": ["5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "7.1", "8.2"] },
    { "id": 7, "tasks": ["7.2", "9.1", "9.3"] },
    { "id": 8, "tasks": ["9.2"] },
    { "id": 9, "tasks": ["9.4"] }
  ]
}
```
