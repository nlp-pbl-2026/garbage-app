# Implementation Plan: GPS District Detection

## Overview

GPS地区自動判定機能の実装。Flutter フロントエンドにて端末のGPS座標取得→逆ジオコーディング→choumei.csvマッチングの一連のパイプラインを構築し、既存のRegionSelectionScreenおよびSettingsScreenに「現在地から設定」ボタンを追加する。Riverpod + Service層の既存アーキテクチャに従い、LocationService・ReverseGeocodingService・DistrictMatcherServiceの3サービスとGpsDetectionProviderを新規実装する。

## Tasks

- [x] 1. 依存パッケージの追加とデータ基盤の構築
  - [x] 1.1 pubspec.yaml に必要パッケージを追加し、choumei.csv をアセットに登録する
    - `geolocator` パッケージを追加（GPS座標取得用）
    - `geocoding` パッケージを追加（逆ジオコーディング用）
    - `csv` パッケージを追加（CSVパース用）
    - `assets/` に `choumei.csv` を配置し、`pubspec.yaml` の `flutter.assets` に登録
    - _Requirements: 3.1, 4.1_

  - [x] 1.2 GPS関連のデータモデルと例外クラスを定義する
    - `lib/models/gps_detection.dart` を作成
    - `GpsCoordinate` クラス（latitude, longitude, accuracy, `isAccurate` getter）を定義
    - `GeocodedAddress` クラス（prefecture, city, town, subTown, fullAddress）を定義
    - `DistrictMatchResult` クラス（districtNumber, districtName, matchedTown）を定義
    - `ChoumeiEntry` クラス（districtNumber, districtName, townCode, townName, oldCityName）を定義
    - `LocationPermissionStatus` enum を定義（granted, denied, deniedForever, serviceDisabled）
    - `GpsDetectionException` sealed クラスと各サブクラス（LocationPermissionDeniedException, LocationServiceDisabledException, LocationTimeoutException, LocationInaccurateException, GeocodingFailedException, OutOfAreaException, DistrictNotFoundException）を定義
    - _Requirements: 1.4, 2.2, 2.3, 3.3, 4.3, 4.4, 7.1_

- [x] 2. サービス層の実装
  - [x] 2.1 GpsLocationService を実装する
    - `lib/services/gps_location_service.dart` を作成
    - `checkPermission()` で権限状態を確認（`geolocator` の `Geolocator.checkPermission()` をラップ）
    - `requestPermission()` で権限をリクエスト（`Geolocator.requestPermission()` をラップ）
    - `isLocationServiceEnabled()` で端末の位置情報サービス有効状態を確認
    - `getCurrentPosition()` でGPS座標を取得（タイムアウト5秒、精度500m以内バリデーション付き）
    - 権限拒否時は `LocationPermissionDeniedException`、サービス無効時は `LocationServiceDisabledException`、タイムアウト時は `LocationTimeoutException`、精度不足時は `LocationInaccurateException` をスロー
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

  - [x] 2.2 ReverseGeocodingService を実装する
    - `lib/services/reverse_geocoding_service.dart` を作成
    - `getAddressFromCoordinates(double latitude, double longitude)` で座標を日本語住所に変換
    - `geocoding` パッケージの `placemarkFromCoordinates` を使用
    - 変換結果から `GeocodedAddress`（prefecture, city, town, subTown）を生成
    - 失敗時は `GeocodingFailedException` をスロー
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 2.3 DistrictMatcherService を実装する
    - `lib/services/district_matcher_service.dart` を作成
    - `loadChoumeiData()` で `assets/choumei.csv` を読み込み `List<ChoumeiEntry>` にパース・キャッシュ
    - `matchDistrict(GeocodedAddress address)` でマッチングロジックを実装
    - マッチング手順：(1) city が「松山市」か確認、(2) town+subTown で完全一致検索、(3) town のみで前方一致検索
    - 全角/半角数字の正規化ロジック（丁目の数字表記統一）を実装
    - 松山市外の場合は `OutOfAreaException`、マッチなしの場合は `DistrictNotFoundException` をスロー
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x]* 2.4 GpsCoordinate の精度バリデーションのプロパティテストを書く
    - **Property 1: GPS精度バリデーション**
    - `test/services/gps_coordinate_property_test.dart` を作成
    - `glados` を使い、ランダムな精度値（0.0〜10000.0）で `isAccurate` の正しさを検証
    - **Validates: Requirements 1.4**

  - [x]* 2.5 DistrictMatcherService の町名マッチングのプロパティテストを書く
    - **Property 2: 町名マッチングの正確性**
    - `test/services/district_matcher_property_test.dart` を作成
    - `glados` を使い、choumei.csv から取得した実在町名で正しい地区が返ることを検証
    - **Validates: Requirements 4.1, 4.2, 4.5**

  - [x]* 2.6 DistrictMatcherService のエリア外検出のプロパティテストを書く
    - **Property 3: エリア外検出**
    - 同テストファイルに追加
    - `glados` を使い、「松山市」以外の市区町村名で `OutOfAreaException` がスローされることを検証
    - **Validates: Requirements 4.3**

  - [x]* 2.7 DistrictMatcherService の未マッチ町名エラーのプロパティテストを書く
    - **Property 4: 未マッチ町名のエラーハンドリング**
    - 同テストファイルに追加
    - `glados` を使い、choumei.csv に存在しないランダムな町名文字列で `DistrictNotFoundException` がスローされることを検証
    - **Validates: Requirements 4.4**

- [x] 3. Checkpoint - サービス層確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 状態管理（Provider）の実装
  - [x] 4.1 GpsDetectionProvider を実装する
    - `lib/providers/gps_detection_provider.dart` を作成
    - `GpsDetectionState` sealed クラス（Idle, Loading, Success, Error）を定義
    - `GpsDetectionNotifier`（StateNotifier）を実装
    - `detectDistrict()` メソッド：権限確認→GPS取得→逆ジオコーディング→マッチングの一連のフローを実行
    - 各ステップの失敗を `GpsDetectionError` 状態にマッピングし、userMessage をセット
    - `reset()` メソッドで状態を Idle に戻す
    - サービスプロバイダー（`gpsLocationServiceProvider`, `reverseGeocodingServiceProvider`, `districtMatcherServiceProvider`）を定義
    - `gpsDetectionProvider` を `StateNotifierProvider` として公開
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 7.1, 7.2, 7.3_

  - [x]* 4.2 GpsDetectionNotifier のユニットテストを書く
    - `test/providers/gps_detection_provider_test.dart` を作成
    - 正常系：各サービスの成功レスポンスで Success 状態に遷移することを確認
    - 異常系：各例外が発生した場合に Error 状態に正しい userMessage で遷移することを確認
    - reset() で Idle に戻ることを確認
    - _Requirements: 7.1, 7.2, 7.3_

  - [x]* 4.3 RegionSetting 保存フォーマットのプロパティテストを書く
    - **Property 5: RegionSetting保存フォーマットの一貫性**
    - `test/providers/region_setting_format_property_test.dart` を作成
    - `glados` を使い、ランダムな `DistrictMatchResult` から生成される RegionSetting が正しいフィールド構造を持ち、districtId が `{municipalityId}-{districtNumber}` 形式であることを検証
    - **Validates: Requirements 5.2, 5.4**

- [x] 5. UI の実装
  - [x] 5.1 RegionSelectionScreen に「現在地から設定」ボタンを追加する
    - `lib/screens/region_selection_screen.dart` を編集
    - 3段階選択UIの上部に「現在地から設定」ボタンを追加（GPSアイコン `Icons.my_location` 付き）
    - ボタンタップで `gpsDetectionProvider` の `detectDistrict()` を呼び出し
    - GPS判定処理中はボタンを無効化しローディングインジケーター（CircularProgressIndicator）を表示
    - _Requirements: 6.1, 6.3, 6.4_

  - [x] 5.2 GPS判定成功時の確認ダイアログを実装する
    - `GpsDetectionSuccess` 状態で確認ダイアログを表示
    - ダイアログ内容：「都道府県: 愛媛県、市区町村: 松山市、地区: {判定された地区名}」
    - 「この地域で設定」ボタン：RegionSetting を生成し、`regionSettingProvider` の `saveSetting()` で SharedPreferences に保存
    - 「キャンセル」ボタン：ダイアログを閉じて手動選択モードに戻る
    - 保存する RegionSetting は手動選択と同一フォーマット（prefectureId: "38", municipalityId: "38201", districtId: "38201-{districtNumber}"）
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 5.3 エラー時の SnackBar 表示を実装する
    - `GpsDetectionError` 状態で SnackBar にエラーメッセージを表示（表示時間3秒）
    - エラー後も手動選択UIを利用可能な状態に維持
    - エラー後も「現在地から設定」ボタンを再タップ可能にする（状態を Idle にリセット）
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 5.4 SettingsScreen に「現在地から再設定」ボタンを追加する
    - `lib/screens/settings_screen.dart` を編集
    - 地域設定セクションに「現在地から再設定」ボタンを追加
    - タップ時の動作は RegionSelectionScreen と同様のフロー（detectDistrict → 確認ダイアログ → 保存）
    - _Requirements: 6.2_

  - [x]* 5.5 RegionSelectionScreen のウィジェットテストを書く
    - `test/screens/region_selection_gps_test.dart` を作成
    - 「現在地から設定」ボタンの表示位置確認（3段階選択UIの上部）
    - ローディング状態でのボタン無効化確認
    - 確認ダイアログの表示内容確認
    - エラー時の SnackBar 表示確認
    - エラー後の手動選択UI利用可能確認
    - _Requirements: 6.1, 6.3, 6.4, 7.1, 7.2, 7.3_

- [x] 6. Final checkpoint - 全テスト確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (Properties 1-5 from design)
- Unit/widget tests validate specific scenarios and edge cases
- Frontend uses `glados` (already in dev_dependencies) for property tests
- `geolocator`, `geocoding`, `csv` パッケージを新規追加する必要あり
- `permission_handler` は既に pubspec.yaml に含まれている
- choumei.csv は既にリポジトリルートに存在するため、`assets/` にコピーまたはシンボリックリンクで配置する
- 既存の `RegionSetting` モデル・`RegionService`・`regionSettingProvider` を再利用する

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "2.5", "2.6", "2.7"] },
    { "id": 4, "tasks": ["4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 7, "tasks": ["5.5"] }
  ]
}
```
