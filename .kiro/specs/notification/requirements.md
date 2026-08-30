# Requirements Document

## Introduction

ゴミ出しアプリのコア通知機能。ユーザーの地区設定に基づき、次回のゴミ収集日の「前日」と「当日」にローカル通知（端末内スケジュール、バックエンド不要）を配信する。リマインダー通知全体の有効化・無効化、OS通知権限のリクエストと拒否時のハンドリング、通知時刻のユーザー変更、通知タップ時の該当画面への遷移、および通知設定の永続化を提供する。

ゴミ種別（可燃・資源・プラスチック・ペットボトル・危険）ごとの通知ON/OFFカスタマイズは別スペック `notification-customization` が担当する。本スペックは、そのカスタマイズが適用される土台となるコア通知基盤を定義する。

## Glossary

- **NotificationService**: flutter_local_notifications を使用してローカル通知をスケジュール・キャンセルするコアサービスコンポーネント
- **ReminderNotification**: 次回ゴミ収集日をユーザーに知らせるローカル通知
- **EveningNotification**: 収集日の前日、ユーザー指定時刻（デフォルト20:00）に配信される通知
- **MorningNotification**: 収集日の当日、ユーザー指定時刻（デフォルト06:00）に配信される通知
- **ReminderEnabledFlag**: リマインダー通知全体の有効/無効を表すマスタースイッチの状態値
- **District_ID**: ユーザーが選択したゴミ収集地区を識別するID（例: "38201-10"）
- **ScheduleService**: 指定日・指定地区のゴミ収集カテゴリ一覧を返す既存サービス
- **CollectionCategory**: ある日に収集されるゴミ分類（可燃・資源・プラスチック・ペットボトル・危険 等）
- **NotificationPermission**: OS（Android/iOS）がアプリに付与するローカル通知の表示許可
- **NotificationTapAction**: 通知タップ時にアプリが実行する画面遷移動作
- **SharedPreferences**: 端末ローカルにKey-Value形式でデータを永続化するストレージ
- **ScheduleWindow**: 通知を先読みしてスケジュールする対象期間（本日から7日間）

## Requirements

### Requirement 1: リマインダー通知全体の有効化・無効化

**User Story:** ユーザーとして、ゴミ収集日のリマインダー通知全体を1つのスイッチでON/OFFしたい。不要なときは通知を止められるようにしたい。

#### Acceptance Criteria

1. WHEN ユーザーがリマインダー通知を有効化した場合、THE NotificationService SHALL ReminderEnabledFlagをtrueとしてSharedPreferencesに保存する
2. WHEN ユーザーがリマインダー通知を有効化した場合、THE NotificationService SHALL 選択中のDistrict_IDに基づいてScheduleWindow内の通知をスケジュールする
3. WHEN ユーザーがリマインダー通知を無効化した場合、THE NotificationService SHALL ReminderEnabledFlagをfalseとしてSharedPreferencesに保存する
4. WHEN ユーザーがリマインダー通知を無効化した場合、THE NotificationService SHALL スケジュール済みの全ReminderNotificationをキャンセルする
5. WHILE ReminderEnabledFlagがfalseの状態、THE NotificationService SHALL 新規のReminderNotificationをスケジュールしない
6. WHEN リマインダー通知が無効化された時点で既にOSに配信処理中の通知が存在する場合、THE NotificationService SHALL 配信処理中の通知の完了を許容する

### Requirement 2: 通知権限のリクエストとハンドリング

**User Story:** ユーザーとして、通知を受け取るために必要なOSの許可を求められ、拒否した場合でもアプリが正常に動作してほしい。

#### Acceptance Criteria

1. WHEN ユーザーが初めてリマインダー通知を有効化した場合、THE NotificationService SHALL OSに対してNotificationPermissionをリクエストする
2. IF NotificationPermissionのリクエスト送信自体が失敗した場合、THEN THE NotificationService SHALL リマインダー通知の有効化を中止し、ReminderEnabledFlagをfalseのまま保持する
3. WHEN NotificationPermissionが付与された場合、THE NotificationService SHALL ReminderNotificationのスケジュールを継続する
4. IF ユーザーがNotificationPermissionを拒否した場合、THEN THE NotificationService SHALL ReminderEnabledFlagをfalseのまま保持し、権限が必要である旨のメッセージをユーザーに提示する
5. IF NotificationPermissionが拒否されている状態でリマインダー通知の有効化が試行された場合、THEN THE NotificationService SHALL OS設定画面への導線を含む案内をユーザーに提示する

### Requirement 3: 前日・当日通知のスケジューリング

**User Story:** ユーザーとして、ゴミ収集日の前日と当日にリマインダーを受け取り、当日に収集されるゴミ種別を把握したい。

#### Acceptance Criteria

1. WHILE ReminderEnabledFlagがtrueの状態、THE NotificationService SHALL ScheduleWindow（本日から7日間）内の各収集日について、前日のEveningNotification時刻にEveningNotificationをスケジュールする
2. WHILE ReminderEnabledFlagがtrueの状態、THE NotificationService SHALL ScheduleWindow内の各収集日について、当日のMorningNotification時刻にMorningNotificationをスケジュールする
3. THE NotificationService SHALL 各ReminderNotificationの本文に、対象日に収集されるCollectionCategoryのラベルを含める
4. IF CollectionCategoryのラベルの取得に失敗しReminderNotification本文に含められない場合、THEN THE NotificationService SHALL その通知を無効として扱い、スケジュールしない
5. WHEN 対象の通知配信時刻が現在時刻以前である場合、THE NotificationService SHALL その通知をスケジュールしない
6. WHEN 指定日・指定地区に収集予定のCollectionCategoryが存在しない場合、THE NotificationService SHALL その日のReminderNotificationをスケジュールしない
7. WHEN 選択中のDistrict_IDが変更された場合、THE NotificationService SHALL スケジュール済みのReminderNotificationを再計算して更新する

### Requirement 4: 通知時刻のカスタマイズ

**User Story:** ユーザーとして、前日通知と当日通知の配信時刻を自分の生活リズムに合わせて変更したい。

#### Acceptance Criteria

1. WHEN 通知時刻が設定されていない場合、THE NotificationService SHALL EveningNotification時刻を20時00分、MorningNotification時刻を06時00分として扱う
2. WHEN ユーザーがEveningNotification時刻を変更した場合、THE NotificationService SHALL 指定された時（0〜23）と分（0〜59）をSharedPreferencesに保存する
3. WHEN ユーザーがMorningNotification時刻を変更した場合、THE NotificationService SHALL 指定された時（0〜23）と分（0〜59）をSharedPreferencesに保存する
4. IF 通知時刻のSharedPreferencesへの保存に失敗した場合、THEN THE NotificationService SHALL 時刻変更を保存前の値に戻し、保存に失敗した旨のエラーメッセージをユーザーに提示する
5. WHEN 通知時刻が変更されSharedPreferencesへの保存が成功した場合、THE NotificationService SHALL 変更後の時刻でスケジュール済みのReminderNotificationを再計算して更新する

### Requirement 5: 通知タップ時の画面遷移

**User Story:** ユーザーとして、通知をタップしたら該当するゴミ収集日の詳細を確認できる画面をすぐに開きたい。

#### Acceptance Criteria

1. WHEN ユーザーがReminderNotificationをタップした場合、THE NotificationService SHALL NotificationTapActionとしてゴミ収集日を確認できる画面をアプリ内で開く
2. IF アプリが起動していない状態でReminderNotificationがタップされた場合、THEN THE NotificationService SHALL アプリを起動したうえでゴミ収集日を確認できる画面を開く

### Requirement 6: 通知設定の永続化と復元

**User Story:** ユーザーとして、アプリを再起動したり端末を再起動しても通知設定が保持され、リマインダーが継続してほしい。

#### Acceptance Criteria

1. THE NotificationService SHALL ReminderEnabledFlag、District_ID、EveningNotification時刻、MorningNotification時刻をSharedPreferencesに永続化する
2. WHEN アプリが起動した場合、THE NotificationService SHALL SharedPreferencesから保存済みの通知設定を読み込む
3. WHILE ReminderEnabledFlagがtrueの状態でアプリが起動した場合、THE NotificationService SHALL 保存済みの設定に基づいてReminderNotificationを再スケジュールする
4. IF 起動時の再スケジュール処理が失敗した場合、THEN THE NotificationService SHALL ReminderEnabledFlagをtrueのまま保持する
5. IF SharedPreferencesからの読み込みに失敗した場合、THEN THE NotificationService SHALL ReminderEnabledFlagをfalse（デフォルト値）として動作する
