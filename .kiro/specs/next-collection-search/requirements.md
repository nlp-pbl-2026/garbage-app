# Requirements Document

## Introduction

カレンダー画面にゴミカテゴリ別の次回収集日検索機能を追加する。ユーザーは全5カテゴリ（可燃ごみ、資源ごみ、プラスチック、ペットボトル、危険ごみ）の次回収集日を一覧で確認でき、特定カテゴリの次回収集日を素早く把握できる。既存の `ScheduleService.getNextCollectionDate()` メソッドを活用し、カレンダー画面内のUIとして提供する。

## Glossary

- **Collection_Search_Panel**: カレンダー画面内に配置される、カテゴリ別次回収集日一覧を表示するUIパネル
- **Category_Card**: 各ゴミカテゴリの次回収集日情報を表示するカード型UI要素
- **Schedule_Service**: 収集スケジュールの計算を担当するサービスクラス（既存）
- **District_ID**: ユーザーが設定済みの地区識別子
- **Garbage_Category**: ゴミ分類カテゴリ（burnable, recyclable, plastic, petBottle, hazardous の5種）
- **Calendar_Screen**: table_calendarを使用した月間収集スケジュール表示画面（既存）

## Requirements

### Requirement 1: カテゴリ別次回収集日一覧表示

**User Story:** As a ユーザー, I want カレンダー画面でカテゴリ別に次回収集日を一覧で確認したい, so that 出したいゴミの収集日を素早く把握できる

#### Acceptance Criteria

1. WHEN Calendar_Screen が表示された時, THE Collection_Search_Panel SHALL 全5カテゴリの次回収集日を一覧形式で表示する
2. THE Collection_Search_Panel SHALL 各カテゴリを Category_Card として表示し、カテゴリ名・次回収集日・カテゴリ色を含む
3. THE Collection_Search_Panel SHALL カテゴリを固定の順序（可燃ごみ、資源ごみ、プラスチック、ペットボトル、危険ごみ）で表示する
4. WHEN Category_Card を表示する時, THE Collection_Search_Panel SHALL 次回収集日を「M月d日（曜日）」形式で表示する

### Requirement 2: 次回収集日の計算

**User Story:** As a ユーザー, I want 今日以降の最も近い収集日をカテゴリごとに知りたい, so that 次にいつ出せるかを正確に把握できる

#### Acceptance Criteria

1. THE Schedule_Service SHALL District_ID と Garbage_Category を入力として今日以降で最も近い収集日を返す
2. WHEN 当月に該当カテゴリの収集日が残っていない場合, THE Schedule_Service SHALL 翌月のスケジュールから次回収集日を探索する
3. WHEN 当月および翌月に該当カテゴリの収集日が存在しない場合, THE Schedule_Service SHALL null を返す

### Requirement 3: 収集日までの残日数表示

**User Story:** As a ユーザー, I want 次の収集日まであと何日かを知りたい, so that 準備のタイミングを判断できる

#### Acceptance Criteria

1. WHEN 次回収集日が今日の場合, THE Category_Card SHALL 「今日」と表示する
2. WHEN 次回収集日が明日の場合, THE Category_Card SHALL 「明日」と表示する
3. WHEN 次回収集日が明後日以降の場合, THE Category_Card SHALL 「あとN日」形式で残日数を表示する

### Requirement 4: データ読み込み状態の表示

**User Story:** As a ユーザー, I want データ読み込み中や取得できない場合に適切なフィードバックを得たい, so that アプリの状態を理解できる

#### Acceptance Criteria

1. WHILE Schedule_Service がデータを読み込み中の間, THE Collection_Search_Panel SHALL 各 Category_Card にローディングインジケーターを表示する
2. IF 地域設定が未完了の場合, THEN THE Collection_Search_Panel SHALL 「地域を設定してください」メッセージを表示する
3. IF 次回収集日が取得できない場合（null）, THEN THE Category_Card SHALL 「予定なし」と表示する

### Requirement 5: カレンダーとの連動

**User Story:** As a ユーザー, I want Category_Card をタップして該当日をカレンダーで確認したい, so that その日の他の収集予定も合わせて確認できる

#### Acceptance Criteria

1. WHEN ユーザーが Category_Card をタップした時, THE Calendar_Screen SHALL 該当する次回収集日をカレンダー上で選択状態にする
2. WHEN ユーザーが Category_Card をタップした時, THE Calendar_Screen SHALL 該当日が表示月と異なる場合にカレンダーの表示月を切り替える

### Requirement 6: 状態管理

**User Story:** As a 開発者, I want カテゴリ別次回収集日をRiverpodで効率的に管理したい, so that 地域設定やスケジュール変更時に自動で再計算される

#### Acceptance Criteria

1. THE Collection_Search_Panel SHALL Riverpod の FutureProvider を使用して各カテゴリの次回収集日を非同期に取得する
2. WHEN 地域設定（District_ID）が変更された時, THE Collection_Search_Panel SHALL 全カテゴリの次回収集日を再計算する
3. THE Collection_Search_Panel SHALL Schedule_Service の既存メソッド getNextCollectionDate を使用して次回収集日を取得する
