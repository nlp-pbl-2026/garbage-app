# Requirements Document

## Introduction

ゴミ品目検索画面に検索履歴機能を追加する。ユーザーが過去に検索したキーワードおよび閲覧した品目の履歴をSharedPreferencesに永続化し、検索画面上の履歴セクションから素早く再検索・再閲覧できるようにする。

## Glossary

- **Search_History_Service**: 検索キーワード履歴および品目閲覧履歴の保存・取得・削除を担当するサービスクラス
- **Search_Screen**: ゴミ品目を検索するための画面。テキスト入力、検索結果表示、よく検索されるもの、検索履歴セクションを含む
- **Keyword_History**: ユーザーが過去に検索実行したキーワードの履歴リスト
- **Item_History**: ユーザーが検索結果から品目詳細画面へ遷移した際に記録される品目閲覧履歴リスト
- **History_Entry**: 履歴の1件分のデータ。キーワードまたは品目ID、タイムスタンプを含む
- **SharedPreferences**: アプリのローカルストレージ。キーバリュー形式でデータを永続化する仕組み

## Requirements

### Requirement 1: キーワード検索履歴の保存

**User Story:** As a ユーザー, I want 検索を実行したキーワードが自動的に保存される, so that 以前調べたキーワードを覚えていなくても再検索できる

#### Acceptance Criteria

1. WHEN ユーザーが2文字以上のキーワードで検索を実行する, THE Search_History_Service SHALL そのキーワードをタイムスタンプとともにKeyword_Historyに新規エントリとして追加する
2. WHEN 同一のキーワードが再度検索される, THE Search_History_Service SHALL 新しいエントリとして追加する（既存エントリは上書きせず残す）
3. THE Search_History_Service SHALL Keyword_Historyの保存件数を最大50件に制限する
4. WHEN Keyword_Historyが50件に達した状態で新しいキーワードが保存される, THE Search_History_Service SHALL 最も古いエントリを削除して新しいエントリを追加する
5. THE Search_History_Service SHALL Keyword_HistoryをSharedPreferencesに永続化する

### Requirement 2: 品目閲覧履歴の保存

**User Story:** As a ユーザー, I want 詳細を確認した品目の履歴が残る, so that 以前調べた品目にすぐアクセスできる

#### Acceptance Criteria

1. WHEN ユーザーが検索結果から品目詳細画面に遷移する, THE Search_History_Service SHALL その品目のIDと品目名をタイムスタンプとともにItem_Historyに新規エントリとして追加する
2. WHEN 同一の品目が再度閲覧される, THE Search_History_Service SHALL 新しいエントリとして追加する（既存エントリは上書きせず残す）
3. THE Search_History_Service SHALL Item_Historyの保存件数を最大50件に制限する
4. WHEN Item_Historyが50件に達した状態で新しい品目が閲覧される, THE Search_History_Service SHALL 最も古いエントリを削除して新しいエントリを追加する
5. THE Search_History_Service SHALL Item_HistoryをSharedPreferencesに永続化する

### Requirement 3: 検索画面での履歴表示

**User Story:** As a ユーザー, I want 検索画面で過去の検索履歴を確認できる, so that すぐに再検索できる

#### Acceptance Criteria

1. WHILE 検索テキストフィールドが空の状態, THE Search_Screen SHALL 「よく検索されるもの」セクションの上に検索履歴セクションを表示する
2. THE Search_Screen SHALL Keyword_Historyを新しい順（タイムスタンプ降順）で表示する
3. THE Search_Screen SHALL Item_HistoryをKeyword_Historyの下に新しい順（タイムスタンプ降順）で表示する
4. WHEN 履歴が1件も存在しない, THE Search_Screen SHALL 検索履歴セクションを非表示にする
5. THE Search_Screen SHALL キーワード履歴と品目閲覧履歴を視覚的に区別して表示する

### Requirement 4: 履歴からの再検索・再閲覧

**User Story:** As a ユーザー, I want 履歴をタップして再検索や品目詳細を直接開きたい, so that 素早く情報にアクセスできる

#### Acceptance Criteria

1. WHEN ユーザーがKeyword_Historyの項目をタップする, THE Search_Screen SHALL そのキーワードを検索テキストフィールドに入力し検索を実行する
2. WHEN ユーザーがItem_Historyの項目をタップする, THE Search_Screen SHALL 該当品目の詳細画面に直接遷移する
3. IF Item_Historyに保存された品目IDに対応する品目データが存在しない, THEN THE Search_Screen SHALL その履歴項目をグレーアウトして非タップ可能にする

### Requirement 5: 履歴の削除

**User Story:** As a ユーザー, I want 不要な履歴を削除したい, so that 履歴リストを整理できる

#### Acceptance Criteria

1. WHEN ユーザーが履歴項目を左スワイプする, THE Search_Screen SHALL その項目の削除ボタンを表示する
2. WHEN ユーザーが削除ボタンをタップする, THE Search_History_Service SHALL 該当のHistory_Entryを削除しSharedPreferencesを更新する
3. WHEN ユーザーが「履歴をすべて削除」ボタンをタップする, THE Search_History_Service SHALL Keyword_HistoryとItem_Historyの全エントリを削除しSharedPreferencesを更新する
4. THE Search_Screen SHALL 検索履歴セクションのヘッダーに「すべて削除」ボタンを表示する

### Requirement 6: 履歴データの永続化

**User Story:** As a ユーザー, I want アプリを閉じても履歴が保持される, so that 次回起動時にも過去の検索履歴を利用できる

#### Acceptance Criteria

1. THE Search_History_Service SHALL アプリ終了後も履歴データがSharedPreferencesに保持されることを保証する
2. WHEN アプリが起動される, THE Search_History_Service SHALL SharedPreferencesからKeyword_HistoryとItem_Historyを読み込む
3. IF SharedPreferencesのデータが破損している, THEN THE Search_History_Service SHALL 破損データを空リストとして初期化しエラーをログ出力する
4. THE Search_History_Service SHALL 履歴データをJSON形式でシリアライズおよびデシリアライズする
5. FOR ALL 有効なHistory_Entry, シリアライズ後にデシリアライズした結果は元のHistory_Entryと等価である（ラウンドトリップ特性）
