# Requirements Document

## Introduction

愛媛県向けゴミ出しアプリケーションに「ホーム画面」を追加する。ログイン（またはスキップ）後、地域設定が完了した時点で、従来のMainScreen（BottomNavigationBar構成）ではなく、まずホーム画面（ダッシュボード）に遷移する。ホーム画面から各機能（検索、カレンダー、設定）へアクセスできるようにし、今日・明日のゴミ出し情報を一目で確認できるようにする。

## Glossary

- **Home_Screen**: ログインおよび地域設定完了後に最初に表示されるダッシュボード画面
- **Collection_Summary**: ホーム画面に表示される今日・明日のゴミ収集予定情報のサマリーセクション
- **Navigation_Card**: ホーム画面に配置される各機能画面（検索、カレンダー、設定）への遷移カード
- **App_Router**: アプリケーション全体の画面遷移を制御するウィジェット（現在のapp.dart内の_AppHome/_AuthCheck/_RegionCheck）
- **Calendar_Screen**: 月間のゴミ収集スケジュールをカレンダー形式で表示する画面
- **Search_Screen**: ゴミ品目を検索し分別方法を確認する画面
- **Settings_Screen**: アプリケーションの設定を変更する画面
- **MainScreen**: 既存のBottomNavigationBar構成の3タブ画面（検索/カレンダー/設定）
- **Region_Setting**: ユーザーが選択した地域情報（都道府県・市区町村・地区）

## Requirements

### Requirement 1: ホーム画面へのナビゲーション変更

**User Story:** As a ユーザー, I want ログインおよび地域設定完了後にホーム画面に遷移する, so that 各機能の概要を一目で確認してからアクセスしたい機能を選択できる

#### Acceptance Criteria

1. WHEN 地域設定が完了している状態でアプリを起動した場合, THE App_Router SHALL MainScreenの代わりにHome_Screenを表示する
2. WHEN ユーザーがログインまたはスキップを完了し地域設定が完了している場合, THE App_Router SHALL Home_Screenへ遷移する
3. WHEN ユーザーが地域選択を完了した場合, THE App_Router SHALL Home_Screenへ遷移する

### Requirement 2: ゴミ収集サマリー表示

**User Story:** As a ユーザー, I want ホーム画面で今日と明日のゴミ出し情報を確認する, so that ゴミ出しの準備を素早くできる

#### Acceptance Criteria

1. WHEN Home_Screenが表示された場合, THE Collection_Summary SHALL 今日のゴミ収集カテゴリを表示する
2. WHEN Home_Screenが表示された場合, THE Collection_Summary SHALL 明日のゴミ収集カテゴリを表示する
3. WHEN 今日または明日にゴミ収集予定がない場合, THE Collection_Summary SHALL 「収集予定なし」のメッセージを表示する
4. WHEN ゴミ収集データの読み込みに失敗した場合, THE Collection_Summary SHALL エラーメッセージとリトライボタンを表示する
5. WHEN ゴミ収集データの読み込み中の場合, THE Collection_Summary SHALL ローディングインジケーターを表示する

### Requirement 3: 各機能への導線カード

**User Story:** As a ユーザー, I want ホーム画面から検索・カレンダー・設定画面にアクセスする, so that 必要な機能に素早く移動できる

#### Acceptance Criteria

1. THE Home_Screen SHALL Search_Screenへの Navigation_Card を表示する
2. THE Home_Screen SHALL Calendar_Screenへの Navigation_Card を表示する
3. THE Home_Screen SHALL Settings_Screenへの Navigation_Card を表示する
4. WHEN ユーザーがSearch_ScreenのNavigation_Cardをタップした場合, THE Home_Screen SHALL Search_Screenへ遷移する
5. WHEN ユーザーがCalendar_ScreenのNavigation_Cardをタップした場合, THE Home_Screen SHALL Calendar_Screenへ遷移する
6. WHEN ユーザーがSettings_ScreenのNavigation_Cardをタップした場合, THE Home_Screen SHALL Settings_Screenへ遷移する

### Requirement 4: 各機能画面からの復帰

**User Story:** As a ユーザー, I want 各機能画面からホーム画面に戻る, so that 他の機能にもアクセスできる

#### Acceptance Criteria

1. WHEN ユーザーが各機能画面で戻る操作を行った場合, THE App_Router SHALL Home_Screenへ戻る
2. THE Home_Screen SHALL 各機能画面から戻った際に画面状態を維持する

### Requirement 5: 地域情報の表示と変更

**User Story:** As a ユーザー, I want ホーム画面で現在設定されている地域を確認し、タップして変更する, so that 正しい地域のゴミ収集情報を見ていることを確認でき、引っ越し等で地域が変わった場合にも対応できる

#### Acceptance Criteria

1. WHEN Home_Screenが表示された場合, THE Home_Screen SHALL 設定済みのRegion_Setting（市区町村名・地区名）をヘッダー部にタップ可能な形式で表示する
2. WHEN ユーザーがヘッダーの地域表示をタップした場合, THE Home_Screen SHALL RegionSelectionScreenへ遷移する
3. WHEN ユーザーがRegionSelectionScreenで地域を再選択した場合, THE App_Router SHALL 新しい地域設定を保存しHome_Screenに戻る
4. WHEN 地域設定が変更された場合, THE Collection_Summary SHALL 新しい地域に基づいたゴミ収集情報に更新する
