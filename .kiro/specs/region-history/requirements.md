# Requirements Document

## Introduction

地域設定の変更履歴を保存し、過去に設定した地域へ簡単に切り替えられる機能。ユーザーが地域設定を変更する際、変更前の設定を履歴として自動保存し、設定画面から過去の地域を選択して即座に切り替えられるようにする。

## Glossary

- **Region_History_Service**: 地域設定の履歴をSharedPreferencesに保存・取得・管理するサービス
- **Region_History_List**: 過去に設定した地域設定のリスト（時系列順）
- **Settings_Screen**: 地域設定の表示・変更・履歴一覧を提供する設定画面
- **Region_Setting**: 都道府県ID・名称、市区町村ID・名称、地区ID・名称を含む地域設定データ
- **History_Entry**: 地域設定と保存日時を含む履歴の1件分のデータ
- **Max_History_Count**: 履歴リストに保存される最大件数（10件）

## Requirements

### Requirement 1: 地域変更時の自動履歴保存

**User Story:** As a ユーザー, I want 地域設定を変更するとき変更前の設定が自動的に履歴に保存される, so that 以前使っていた地域設定を後から確認・復元できる

#### Acceptance Criteria

1. WHEN ユーザーが地域設定を新しい値に変更する, THE Region_History_Service SHALL 変更前の地域設定を保存日時とともにRegion_History_Listの先頭に追加する
2. WHEN 変更前の地域設定がRegion_History_Listに既に存在する場合, THE Region_History_Service SHALL 既存のエントリを削除し新しい保存日時で先頭に再追加する（重複を防止する）
3. WHEN Region_History_Listの件数がMax_History_Countを超える場合, THE Region_History_Service SHALL 最も古いエントリを削除してMax_History_Count以下に保つ
4. IF 履歴の保存処理中にエラーが発生した場合, THEN THE Region_History_Service SHALL エラーをログに記録し、地域変更の本処理には影響を与えない

### Requirement 2: 履歴の永続化

**User Story:** As a ユーザー, I want 地域履歴がアプリを閉じても保持される, so that アプリを再起動しても過去の地域設定を確認・切り替えできる

#### Acceptance Criteria

1. THE Region_History_Service SHALL Region_History_ListをJSON形式にシリアライズしてSharedPreferencesに保存する
2. WHEN アプリが起動する, THE Region_History_Service SHALL SharedPreferencesからRegion_History_Listをデシリアライズして復元する
3. IF SharedPreferencesから読み込んだデータが不正なJSON形式の場合, THEN THE Region_History_Service SHALL 空のRegion_History_Listを返し、不正データを消去する
4. THE Region_History_Service SHALL Region_History_ListをシリアライズしたJSON文字列をパースした結果が元のRegion_History_Listと等価になる（ラウンドトリップ整合性）

### Requirement 3: 履歴一覧の表示

**User Story:** As a ユーザー, I want 設定画面で過去に設定した地域の一覧を確認できる, so that どの地域を以前使っていたか把握できる

#### Acceptance Criteria

1. THE Settings_Screen SHALL Region_History_Listの内容を保存日時の新しい順に一覧表示する
2. WHEN Region_History_Listが空の場合, THE Settings_Screen SHALL 履歴セクションに「履歴はありません」というメッセージを表示する
3. THE Settings_Screen SHALL 各History_Entryについて市区町村名、地区名、および保存日時を表示する
4. THE Settings_Screen SHALL 保存日時を「yyyy/MM/dd」形式で表示する

### Requirement 4: 履歴からの地域切り替え

**User Story:** As a ユーザー, I want 履歴一覧から過去の地域を選択して現在の設定に反映できる, so that 地域選択画面を経由せず素早く以前の地域に戻せる

#### Acceptance Criteria

1. WHEN ユーザーが履歴一覧のHistory_Entryをタップする, THE Settings_Screen SHALL 確認ダイアログを表示する
2. WHEN ユーザーが確認ダイアログで「変更」を選択する, THE Region_History_Service SHALL 現在の地域設定を履歴に保存し、選択されたHistory_Entryの地域設定を現在の設定として適用する
3. WHEN 履歴からの地域切り替えが成功する, THE Settings_Screen SHALL 「地域設定を変更しました」というスナックバーを表示する
4. IF 履歴からの地域切り替え中にエラーが発生した場合, THEN THE Settings_Screen SHALL 変更前の設定を維持し、エラーメッセージをスナックバーで表示する

### Requirement 5: 履歴の個別削除

**User Story:** As a ユーザー, I want 不要な履歴エントリを個別に削除できる, so that 履歴リストを整理して必要な地域だけを残せる

#### Acceptance Criteria

1. WHEN ユーザーがHistory_Entryを左にスワイプする, THE Settings_Screen SHALL 削除ボタンを表示する
2. WHEN ユーザーが削除ボタンをタップする, THE Region_History_Service SHALL 該当のHistory_EntryをRegion_History_Listから削除し永続化する
3. WHEN 削除が完了する, THE Settings_Screen SHALL 「履歴を削除しました」というスナックバーを表示する
