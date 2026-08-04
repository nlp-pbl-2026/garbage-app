# Requirements Document

## Introduction

既存GPS地区自動判定機能の改善・拡張。UXの向上（複数候補表示、設定誘導、再試行ボタン）、精度・信頼性の強化（ファジーマッチング、キャッシュ、オフライン対応）、コード品質の改善（DI化、プロパティテスト実装）、将来拡張への対応（複数エリアサポート、バックグラウンド再検出）を含む包括的な改善スペックである。

## Glossary

- **District_Matcher**: 逆ジオコーディングで得られた住所をchoumei_csvの町名データと照合し、対応する地区を特定するコンポーネント
- **Location_Service**: GPSから端末の位置情報座標（緯度・経度）を取得するサービス
- **Reverse_Geocoder**: GPS座標を住所文字列に変換するコンポーネント
- **GPS_Detection_Provider**: GPS地区判定の状態管理を担当するRiverpod StateNotifier
- **Region_Selection_Screen**: 都道府県→市区町村→地区を選択する画面
- **Settings_Screen**: アプリの設定画面
- **choumei_csv**: 地区番号・地区名・町名の対応データ（assets/choumei.csv）
- **Geocoding_Cache**: セッション内で逆ジオコーディング結果を一時保存するキャッシュ機構
- **Address_Normalizer**: 住所文字列のバリエーション（大字、字、スペース差異等）を正規化するコンポーネント
- **Area_Config**: 対応エリア（市区町村）ごとの設定情報を管理する構造体
- **GeoJSON_Resolver**: ローカルポリゴンデータにより座標から地区を判定するオフラインコンポーネント
- **Background_Location_Monitor**: バックグラウンドで位置変化を検出し地区移動を提案するコンポーネント
- **SnackBar**: 画面下部に一時的なメッセージを表示するMaterial Designウィジェット
- **openAppSettings**: geolocatorパッケージが提供する端末設定アプリへの遷移API

## Requirements

### Requirement 1: 複数候補地区の表示と選択

**User Story:** As a ユーザー, I want 前方一致で複数の地区候補がある場合に候補リストから選択したい, so that 誤った地区が自動選択されることを防げる。

#### Acceptance Criteria

1. WHEN District_Matcherの前方一致検索で複数の町名候補がヒットした時, THE GPS_Detection_Provider SHALL 全候補をリストとしてUIに返す
2. WHEN 複数の地区候補が返された時, THE Region_Selection_Screen SHALL 候補リストをボトムシート形式で、choumei_csvの町名カラムの昇順（Unicode順）で表示する
3. WHEN ユーザーが候補リストから1件を選択した時, THE Region_Selection_Screen SHALL 選択された地区の確認ダイアログを表示する
4. WHILE 候補リストのボトムシートが表示されている時, WHEN ユーザーがボトムシート外の領域をタップした時, THE Region_Selection_Screen SHALL 候補リストを閉じて手動選択モードに戻る
5. THE District_Matcher SHALL 候補リストの各項目に地区名と町名の両方を表示するためのデータを返す
6. IF 前方一致検索の候補数が50件を超えた場合, THEN THE GPS_Detection_Provider SHALL 先頭50件のみをリストとしてUIに返し、候補が多すぎる旨のメッセージを付与する

### Requirement 2: 設定アプリへの誘導ボタン

**User Story:** As a ユーザー, I want 権限拒否・位置情報無効のエラー時にワンタップで設定アプリを開きたい, so that 手動で設定アプリを探す手間を省ける。

#### Acceptance Criteria

1. IF ユーザーが位置情報権限を拒否した場合, THEN THE Region_Selection_Screen SHALL SnackBarにエラーメッセージと「設定を開く」アクションボタンを表示し、ユーザーが閉じるか「設定を開く」をタップするまでSnackBarを維持する
2. IF 端末の位置情報サービスが無効な場合, THEN THE Region_Selection_Screen SHALL SnackBarにエラーメッセージと「設定を開く」アクションボタンを表示し、ユーザーが閉じるか「設定を開く」をタップするまでSnackBarを維持する
3. IF ユーザーが位置情報権限を拒否した場合, THEN THE Settings_Screen SHALL SnackBarにエラーメッセージと「設定を開く」アクションボタンを表示し、ユーザーが閉じるか「設定を開く」をタップするまでSnackBarを維持する
4. IF 端末の位置情報サービスが無効な場合, THEN THE Settings_Screen SHALL SnackBarにエラーメッセージと「設定を開く」アクションボタンを表示し、ユーザーが閉じるか「設定を開く」をタップするまでSnackBarを維持する
5. WHEN ユーザーが「設定を開く」ボタンをタップした時, THE Location_Service SHALL 端末のアプリ設定画面を起動する
6. WHEN ユーザーが設定アプリから戻った時, THE Region_Selection_Screen SHALL 「現在地から設定」ボタンを再タップ可能な状態で表示し、自動的にGPS判定を再実行しない
7. WHILE SnackBarに「設定を開く」アクションボタンが表示されている間, THE Region_Selection_Screen SHALL エラーメッセージテキストとアクションボタンの両方を同時に視認可能な状態で維持する

### Requirement 3: 再試行ボタンの追加

**User Story:** As a ユーザー, I want タイムアウトや精度不足のエラー時にワンタップで再試行したい, so that 手動でボタンを探し直す手間なく再判定できる。

#### Acceptance Criteria

1. IF GPS座標取得がタイムアウトした場合, THEN THE Region_Selection_Screen SHALL SnackBarにエラーメッセージと「再試行」アクションボタンを表示し、SnackBarはユーザーが「再試行」をタップするか10秒経過するまで表示を維持する
2. IF GPS座標の精度が不十分な場合, THEN THE Region_Selection_Screen SHALL SnackBarにエラーメッセージと「再試行」アクションボタンを表示し、SnackBarはユーザーが「再試行」をタップするか10秒経過するまで表示を維持する
3. IF Settings_ScreenでGPS座標取得がタイムアウトまたは精度不足となった場合, THEN THE Settings_Screen SHALL SnackBarにエラーメッセージと「再試行」アクションボタンを表示し、SnackBarはユーザーが「再試行」をタップするか10秒経過するまで表示を維持する
4. WHEN ユーザーが「再試行」ボタンをタップした時, THE Location_Service SHALL GPS地区判定フローを権限チェックから再実行し、表示中のSnackBarを即座に非表示にする
5. WHILE 再試行が実行中の時, THE Region_Selection_Screen SHALL ローディングインジケータを表示し「現在地から設定」ボタンを無効化する
6. WHILE 再試行が実行中の時, THE Settings_Screen SHALL ローディングインジケータを表示し「現在地から再設定」ボタンを無効化する
7. IF 再試行が再度失敗した場合, THEN THE Region_Selection_Screen SHALL 再度SnackBarに「再試行」アクションボタンを表示し、再試行回数に上限を設けない

### Requirement 4: ファジー住所マッチング

**User Story:** As a システム, I want 逆ジオコーディング結果の住所表記バリエーションに対応したい, so that マッチング精度を向上させ判定失敗を減らせる。

#### Acceptance Criteria

1. THE Address_Normalizer SHALL 住所文字列から町名の直前に出現する「大字」プレフィックスを除去して正規化する（「大字」の除去は「字」の除去より先に実行する）
2. THE Address_Normalizer SHALL 住所文字列から町名の直前に出現する「字」プレフィックスを除去して正規化する（「大字」除去後の文字列に対して適用する）
3. THE Address_Normalizer SHALL 住所文字列中の全角スペース（U+3000）・半角スペース（U+0020）を除去して正規化する
4. THE Address_Normalizer SHALL 住所文字列中の全角数字（U+FF10〜U+FF19）を対応する半角数字（U+0030〜U+0039）に変換して正規化する
5. WHEN District_Matcherが住所マッチングを実行する時, THE District_Matcher SHALL 正規化前の原文で照合を試行し、一致が見つからない場合にのみ正規化後の文字列で照合を試行する
6. THE Address_Normalizer SHALL 正規化処理によってchoumei_csvに存在する町名が照合不能になる変換を行わない（正規化後の文字列がchoumei_csv内の正規化済み町名と一致可能であること）
7. IF Address_Normalizerに空文字列またはnullが入力された場合, THEN THE Address_Normalizer SHALL 正規化をスキップし空文字列を返す
8. WHEN 正規化前の原文と正規化後の文字列がそれぞれ異なる地区に一致した場合, THE District_Matcher SHALL 正規化前の原文による一致結果を優先して返す

### Requirement 5: 逆ジオコーディング結果のキャッシュ

**User Story:** As a システム, I want 同一セッション内で逆ジオコーディング結果をキャッシュしたい, so that 同じ場所での繰り返しタップ時にAPI呼び出しを削減できる。

#### Acceptance Criteria

1. WHEN 逆ジオコーディングが成功した時, THE Geocoding_Cache SHALL リクエスト座標（緯度・経度）と住所文字列のペアを挿入時刻とともにメモリ上に保存する
2. WHEN 過去にキャッシュ済みの座標から半径50メートル以内の座標でリクエストされた時, THE Geocoding_Cache SHALL APIを呼び出さずキャッシュされた結果を返し、複数のキャッシュエントリが50メートル以内に該当する場合は最も距離が近いエントリの結果を返す
3. WHEN アプリのセッションが終了した時（プロセス終了時）, THE Geocoding_Cache SHALL すべてのキャッシュエントリを破棄する
4. THE Geocoding_Cache SHALL キャッシュエントリ数の上限を100件に制限する
5. WHEN キャッシュが上限100件に達した状態で新しいエントリを追加する時, THE Geocoding_Cache SHALL 挿入時刻が最も古いエントリを1件削除してから新しいエントリを追加する（FIFO方式）

### Requirement 6: オフライン逆ジオコーディング

**User Story:** As a ユーザー, I want ネットワーク接続なしでもGPS地区判定を利用したい, so that オフライン環境でも地域設定を完了できる。

#### Acceptance Criteria

1. THE GeoJSON_Resolver SHALL 松山市の全44地区の地区境界ポリゴンデータをGeoJSON形式でアプリバンドルに含む
2. WHEN GPS座標が取得された時, THE GeoJSON_Resolver SHALL 逆ジオコーディングAPIより先にローカルポリゴンデータを使用して座標がどの地区に含まれるか判定し、200ミリ秒以内に結果を返す
3. IF GeoJSON_Resolverによる判定が成功した場合, THEN THE GPS_Detection_Provider SHALL 逆ジオコーディングAPIの呼び出しをスキップし、ポリゴン判定で得られた地区番号・地区名をDistrictMatchResultとして使用する
4. IF GeoJSON_Resolverによる判定が失敗した場合（座標がどのポリゴンにも含まれない）, THEN THE GPS_Detection_Provider SHALL 従来の逆ジオコーディング+マッチングフローにフォールバックする
5. THE GeoJSON_Resolver SHALL ポリゴンデータのロードをアプリ起動時に非同期で行いUIをブロックしない
6. IF ポリゴンデータのロードが完了する前にGPS判定がリクエストされた場合, THEN THE GPS_Detection_Provider SHALL ポリゴン判定をスキップして従来の逆ジオコーディング+マッチングフローを実行する

### Requirement 7: サービスのテスタビリティ向上（DI化）

**User Story:** As a 開発者, I want GpsLocationServiceを抽象インターフェースの背後に配置し依存性を注入可能にしたい, so that ユニットテストでサービスをモック化できる。

#### Acceptance Criteria

1. THE Location_Service SHALL 抽象クラス（インターフェース）として定義され、checkPermission、requestPermission、isLocationServiceEnabled、getCurrentPositionの全公開メソッドを抽象メソッドとして宣言する
2. THE Location_Service SHALL Geolocatorへの依存をコンストラクタ引数として受け取る実装クラスを持つ
3. THE GPS_Detection_Provider SHALL Location_Serviceの具象型ではなく抽象型に依存する
4. WHEN テスト環境でLocation_Serviceのモックが注入された時, THE GPS_Detection_Provider SHALL モックの返す値を使用して動作する
5. THE Reverse_Geocoder SHALL 同様に抽象クラスとして定義され、getAddressFromCoordinatesメソッドを抽象メソッドとして宣言し、テスト時にモック可能な構造を持つ
6. THE District_Matcher SHALL 同様に抽象クラスとして定義され、loadChoumeiDataおよびmatchDistrictメソッドを抽象メソッドとして宣言する

### Requirement 8: プロパティベーステストの実装

**User Story:** As a 開発者, I want 初期実装時にスキップされたプロパティテスト（Property 1〜5）を実装したい, so that マッチングロジックの網羅的な正確性を保証できる。

#### Acceptance Criteria

1. THE テストスイート SHALL gladosパッケージを使用してProperty 1（GPS精度バリデーション: 精度が500m以下なら有効、超えたら無効）のプロパティテストをランダムな精度値（0.0〜10000.0）で実装する
2. THE テストスイート SHALL gladosパッケージを使用してProperty 2（町名マッチングの正確性: choumei.csvに存在する全町名で正しい地区が返る）のプロパティテストを実装する
3. THE テストスイート SHALL gladosパッケージを使用してProperty 3（エリア外検出: 松山市以外の市区町村名でOutOfAreaExceptionが返る）のプロパティテストを実装する
4. THE テストスイート SHALL gladosパッケージを使用してProperty 4（未マッチ町名: choumei.csvに存在しない町名でDistrictNotFoundExceptionが返る）のプロパティテストを実装する
5. THE テストスイート SHALL gladosパッケージを使用してProperty 5（RegionSetting保存フォーマット: districtIdが"{municipalityId}-{districtNumber}"形式である）のプロパティテストを実装する
6. THE テストスイート SHALL 各プロパティテストを最低100回のイテレーションで実行する

### Requirement 9: 複数エリア対応のためのリファクタリング

**User Story:** As a 開発者, I want District_Matcherを複数の市区町村に対応できる構造にリファクタリングしたい, so that 将来的に松山市以外のエリアをサポートできる。

#### Acceptance Criteria

1. THE District_Matcher SHALL エリア識別子（5桁の全国地方公共団体コード、例: "38201"）をパラメータとして受け取り、該当エリアのchoumei_csvデータのみをフィルタリングしてマッチングに使用する
2. THE Area_Config SHALL エリアごとの設定（エリア識別子、市区町村名、対応する旧市町名フィルタ値のリスト、地区番号の最小値と最大値）を定義する構造体として実装する
3. WHEN 新しいエリアのCSVデータとArea_Configエントリが追加された時, THE District_Matcher SHALL District_Matcherのロジックコードを変更せずに新エリアのマッチングを開始できる
4. THE District_Matcher SHALL リファクタリング前のDistrict_Matcherに関する既存ユニットテストおよびプロパティベーステスト全件がコード変更なしで通る状態を維持する
5. THE choumei_csv SHALL 既存の「旧市町名」カラムをエリア識別に利用し、Area_Configの旧市町名フィルタ値と照合することでエリア別データの分離を行う
6. IF District_Matcherに登録されていないエリア識別子が指定された場合, THEN THE District_Matcher SHALL エリア未登録であることを示すエラーを返す
7. WHEN Area_Configにエリアが登録された時, THE Area_Config SHALL 1エリアにつき少なくともエリア識別子、市区町村名、旧市町名フィルタ値1件、地区番号範囲（最小値・最大値の整数ペア）を必須フィールドとして保持する

### Requirement 10: バックグラウンド位置変化による再検出提案

**User Story:** As a ユーザー, I want 地区が変わった可能性がある時に再設定を提案してほしい, so that 引っ越し後に古い地区設定のままゴミ出し情報を見続けることを防げる。

#### Acceptance Criteria

1. WHILE アプリがフォアグラウンドにある時, THE Background_Location_Monitor SHALL 現在のGPS座標と現在設定されている地区の登録時基準座標との直線距離が2km以上であることを検出する
2. WHEN 大幅な位置変化が検出され、かつ前回の提案から24時間以上経過している（または提案履歴が存在しない初回である）時, THE Background_Location_Monitor SHALL 地域設定の更新を促す通知プロンプトを表示する
3. WHEN ユーザーが通知プロンプトで「更新する」を選択した時, THE Background_Location_Monitor SHALL GPS地区判定フローを開始する
4. IF GPS地区判定フローが「更新する」選択後に失敗した場合, THEN THE Background_Location_Monitor SHALL エラーメッセージを表示し、手動で地域選択画面に遷移できるオプションを提示する
5. WHEN ユーザーが通知プロンプトで「後で」を選択した時, THE Background_Location_Monitor SHALL プロンプトを閉じ、次回提案まで24時間のクールダウンを設定する
6. IF ユーザーが通知プロンプトを明示的に選択せずに閉じた場合（戻るボタン、アプリのバックグラウンド移行）, THEN THE Background_Location_Monitor SHALL 「後で」選択と同等の24時間クールダウンを設定する
7. THE Background_Location_Monitor SHALL 位置取得の頻度を最小30分に1回、最大60分に1回の範囲で制限する
8. IF ユーザーが位置情報権限を「アプリ使用中のみ」に設定している場合, THEN THE Background_Location_Monitor SHALL フォアグラウンド時のみ位置変化を監視する
