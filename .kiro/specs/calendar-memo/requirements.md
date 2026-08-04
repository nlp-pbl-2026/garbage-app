# Requirements Document

## Introduction

カレンダー画面の特定の日付にユーザーが自由にメモ（テキスト）を追加・編集・削除できる機能。ゴミ収集スケジュールに加えて、ユーザー独自のメモ（例：「粗大ゴミ予約済み」「引っ越しの片付け」）を日付に紐づけて記録・表示する。

## Glossary

- **Memo_Service**: メモデータの永続化・取得・削除を担当するサービスコンポーネント
- **Calendar_Screen**: table_calendarを使用した月間カレンダー表示画面
- **Memo_Editor**: メモの入力・編集を行うダイアログUI
- **Memo**: 特定の日付に紐づいたユーザー作成テキストデータ（日付、本文、作成日時を含む）
- **Memo_Indicator**: カレンダー上でメモが存在する日付に表示される視覚的マーカー
- **SharedPreferences**: Flutterのローカル軽量データ永続化ストレージ

## Requirements

### Requirement 1: メモの追加

**User Story:** ユーザーとして、カレンダーの特定の日付にメモを追加したい。ゴミ出しに関する予定や覚え書きを日付ごとに記録できるようにするため。

#### Acceptance Criteria

1. WHEN ユーザーが日付を選択してメモ追加操作を行った場合、THE Memo_Editor SHALL テキスト入力ダイアログを表示する
2. WHEN ユーザーがメモ本文を入力して保存操作を行った場合、THE Memo_Service SHALL 入力されたテキストを選択された日付に紐づけて永続化する
3. THE Memo SHALL 日付、本文（1文字以上200文字以下）、作成日時を保持する
4. WHEN ユーザーが空のテキストで保存操作を行った場合、THE Memo_Editor SHALL 保存を実行せずエラーメッセージを表示する
5. WHEN 同一日付に既にメモが存在する状態で追加操作を行った場合、THE Memo_Service SHALL 同一日付に複数のメモを保存する

### Requirement 2: メモの表示

**User Story:** ユーザーとして、カレンダー上でメモがある日付を視覚的に確認し、選択した日付のメモ内容を閲覧したい。メモの存在と内容をすぐに把握できるようにするため。

#### Acceptance Criteria

1. WHEN メモが存在する日付がカレンダーに表示される場合、THE Calendar_Screen SHALL Memo_Indicatorをその日付セルに表示する
2. THE Memo_Indicator SHALL 既存のゴミカテゴリドットマーカーと区別可能なデザインで表示する
3. WHEN ユーザーがメモのある日付を選択した場合、THE Calendar_Screen SHALL 収集予定の下にメモ一覧を表示する
4. THE Calendar_Screen SHALL 各メモの本文と作成日時を表示する
5. WHILE メモデータの読み込み中、THE Calendar_Screen SHALL ローディングインジケーターを表示する

### Requirement 3: メモの編集

**User Story:** ユーザーとして、既存のメモの内容を編集したい。記録した内容を後から修正できるようにするため。

#### Acceptance Criteria

1. WHEN ユーザーが既存メモの編集操作を行った場合、THE Memo_Editor SHALL 現在のメモ本文を初期値としてテキスト入力ダイアログを表示する
2. WHEN ユーザーが編集後のテキストで保存操作を行った場合、THE Memo_Service SHALL 該当メモの本文を更新し永続化する
3. WHEN ユーザーが編集中にキャンセル操作を行った場合、THE Memo_Editor SHALL 変更を破棄してダイアログを閉じる

### Requirement 4: メモの削除

**User Story:** ユーザーとして、不要になったメモを削除したい。古いメモや誤入力したメモを整理できるようにするため。

#### Acceptance Criteria

1. WHEN ユーザーがメモの削除操作を行った場合、THE Calendar_Screen SHALL 削除確認ダイアログを表示する
2. WHEN ユーザーが削除を確認した場合、THE Memo_Service SHALL 該当メモを永続ストレージから削除する
3. WHEN メモ削除後にその日付の全メモが0件になった場合、THE Calendar_Screen SHALL Memo_Indicatorをその日付から除去する

### Requirement 5: データ永続化

**User Story:** ユーザーとして、追加したメモがアプリを閉じても保持されてほしい。次回起動時にも記録が消えないようにするため。

#### Acceptance Criteria

1. THE Memo_Service SHALL メモデータをSharedPreferencesに永続化する
2. WHEN アプリが起動した場合、THE Memo_Service SHALL SharedPreferencesからメモデータを読み込む
3. THE Memo_Service SHALL メモデータをJSON形式でシリアライズおよびデシリアライズする
4. FOR ALL 有効なMemoオブジェクト、シリアライズしてからデシリアライズした結果は元のオブジェクトと等価である（ラウンドトリップ特性）
5. IF SharedPreferencesからの読み込みに失敗した場合、THEN THE Memo_Service SHALL 空のメモリストを返しエラーをログに記録する

### Requirement 6: メモの月間一括取得

**User Story:** ユーザーとして、カレンダーの月を切り替えた際にその月のメモが速やかに表示されてほしい。月間表示での視認性を確保するため。

#### Acceptance Criteria

1. WHEN カレンダーの表示月が変更された場合、THE Memo_Service SHALL 該当月に紐づく全メモを取得する
2. THE Memo_Service SHALL 月間メモ取得を200ミリ秒以内に完了する（100件以下のメモが存在する場合）
3. WHEN 該当月にメモが存在しない場合、THE Memo_Service SHALL 空のMapを返す
