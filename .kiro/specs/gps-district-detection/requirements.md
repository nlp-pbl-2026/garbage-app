# Requirements Document

## Introduction

GPSを使用してユーザーの現在地から住む地区を自動判定する機能。現在の3段階手動選択（都道府県→市区町村→地区）に加え、「現在地から設定」ボタンによりワンタップで地域設定を完了できるようにする。端末のGPS座標を取得し、逆ジオコーディングで住所を取得、choumei.csvの町名データとマッチングすることで松山市内44地区の判定を行う。

## Glossary

- **Location_Service**: GPSから端末の位置情報座標（緯度・経度）を取得するサービス
- **Reverse_Geocoder**: GPS座標を住所文字列に変換するコンポーネント
- **District_Matcher**: 逆ジオコーディングで得られた住所をchoumei.csvの町名データと照合し、対応する地区を特定するコンポーネント
- **Region_Selection_Screen**: 都道府県→市区町村→地区を選択する画面
- **Settings_Screen**: アプリの設定画面
- **choumei_csv**: 地区番号・地区名・町名の対応データ（assets/choumei.csv）
- **RegionSetting**: 都道府県ID・市区町村ID・地区IDを含む地域設定オブジェクト
- **Coverage_Area**: GPS地区判定がサポートされるエリア（松山市内）

## Requirements

### Requirement 1: GPS位置情報の取得

**User Story:** As a ユーザー, I want GPSで現在地の座標を取得したい, so that 位置情報に基づいて地区を自動判定できる。

#### Acceptance Criteria

1. WHEN ユーザーが「現在地から設定」ボタンをタップした時, THE Location_Service SHALL 端末のGPS座標（緯度・経度）を取得する
2. WHILE GPS座標の取得処理中, THE Location_Service SHALL ローディングインジケータを表示する
3. IF GPS座標の取得に5秒以上かかった場合, THEN THE Location_Service SHALL タイムアウトエラーを返す
4. THE Location_Service SHALL 取得した座標の精度を検証し、水平精度が500メートル以内の座標のみを有効とする

### Requirement 2: 位置情報権限の管理

**User Story:** As a ユーザー, I want 位置情報の権限を適切に管理したい, so that プライバシーを維持しながら機能を利用できる。

#### Acceptance Criteria

1. WHEN ユーザーが「現在地から設定」ボタンを初めてタップした時, THE Location_Service SHALL OSの位置情報権限ダイアログを表示する
2. IF ユーザーが位置情報権限を拒否した場合, THEN THE Location_Service SHALL 「位置情報が許可されていません。設定アプリから権限を有効にしてください。」というメッセージを表示する
3. IF 端末の位置情報サービスが無効化されている場合, THEN THE Location_Service SHALL 「位置情報サービスが無効です。端末の設定で有効にしてください。」というメッセージを表示する
4. IF ユーザーが位置情報権限を「今回のみ許可」または「常に許可」で承認した場合, THEN THE Location_Service SHALL GPS座標の取得処理を開始する

### Requirement 3: 逆ジオコーディング

**User Story:** As a システム, I want GPS座標から住所を取得したい, so that 住所情報をもとに地区を特定できる。

#### Acceptance Criteria

1. WHEN 有効なGPS座標が取得された時, THE Reverse_Geocoder SHALL 座標を日本語住所文字列に変換する
2. THE Reverse_Geocoder SHALL 変換結果に市区町村名と町名を含む住所を返す
3. IF 逆ジオコーディングが失敗した場合, THEN THE Reverse_Geocoder SHALL 「住所の取得に失敗しました。手動で地域を選択してください。」というエラーメッセージを返す

### Requirement 4: 地区のマッチング

**User Story:** As a システム, I want 住所から該当する地区を特定したい, so that ユーザーの地域設定を自動で行える。

#### Acceptance Criteria

1. WHEN 逆ジオコーディングで住所が取得された時, THE District_Matcher SHALL 住所の町名部分をchoumei_csvの町名カラムと照合する
2. WHEN 一致する町名が見つかった時, THE District_Matcher SHALL 対応する地区番号から地区ID・地区名を特定する
3. IF 住所が松山市外の場合, THEN THE District_Matcher SHALL 「現在地は対応エリア外です。手動で地域を選択してください。」というメッセージを返す
4. IF 住所が松山市内だがchoumei_csvに一致する町名がない場合, THEN THE District_Matcher SHALL 「現在地の地区を特定できませんでした。手動で地域を選択してください。」というメッセージを返す
5. THE District_Matcher SHALL 町名の丁目表記を含む住所と丁目なしの住所の両方に対応する

### Requirement 5: 地域設定の自動保存

**User Story:** As a ユーザー, I want 判定された地区で自動的に地域設定を完了したい, so that 手動で3段階の選択操作をする手間を省ける。

#### Acceptance Criteria

1. WHEN 地区が正常に特定された時, THE Region_Selection_Screen SHALL 判定結果（都道府県: 愛媛県、市区町村: 松山市、地区: 判定された地区名）を確認ダイアログで表示する
2. WHEN ユーザーが確認ダイアログで「この地域で設定」を選択した時, THE Region_Selection_Screen SHALL RegionSettingを作成しSharedPreferencesに保存する
3. WHEN ユーザーが確認ダイアログで「キャンセル」を選択した時, THE Region_Selection_Screen SHALL ダイアログを閉じて手動選択モードに戻る
4. THE Region_Selection_Screen SHALL 自動判定で保存されたRegionSettingを手動選択で保存されたRegionSettingと同一のフォーマットで保存する

### Requirement 6: UIの統合

**User Story:** As a ユーザー, I want 地域選択画面から簡単にGPS判定機能にアクセスしたい, so that 直感的に機能を利用できる。

#### Acceptance Criteria

1. THE Region_Selection_Screen SHALL 3段階選択UIの上部に「現在地から設定」ボタンを表示する
2. THE Settings_Screen SHALL 地域設定セクションに「現在地から再設定」ボタンを表示する
3. THE Region_Selection_Screen SHALL 「現在地から設定」ボタンにGPSアイコン（my_location）を付与する
4. WHILE GPS判定処理が実行中の時, THE Region_Selection_Screen SHALL 「現在地から設定」ボタンを無効化しローディング状態を表示する

### Requirement 7: エラーハンドリングとフォールバック

**User Story:** As a ユーザー, I want GPS判定が失敗しても手動選択に戻れるようにしたい, so that 機能が使えない状況でも地域設定を完了できる。

#### Acceptance Criteria

1. IF GPS判定プロセスのいずれかのステップで失敗が発生した場合, THEN THE Region_Selection_Screen SHALL エラーメッセージをSnackBarで表示する
2. IF GPS判定が失敗した場合, THEN THE Region_Selection_Screen SHALL 3段階手動選択UIをそのまま利用可能な状態で維持する
3. THE Region_Selection_Screen SHALL エラー発生後も「現在地から設定」ボタンを再タップ可能な状態にする
