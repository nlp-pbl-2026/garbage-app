# Implementation Plan: GPS位置情報による地域自動設定機能

## Overview

既存のFlutter（Dart）/ Riverpodアーキテクチャに従い、GPS位置情報を使った地域自動設定機能を段階的に実装する。依存パッケージの追加・プラットフォーム権限設定 → データモデル・サービス層 → 状態管理層 → UI層の順に構築し、各段階でテストを挟む。既存の手動地域選択機能を阻害せず、フォールバック処理を確実に実装する。

## Tasks

- [x] 1. 依存パッケージ追加とプラットフォーム権限設定
  - [x] 1.1 pubspec.yamlへの依存パッケージ追加
    - `frontend/pubspec.yaml` の `dependencies` に `geolocator: ^6.2.1` と `geocoding: ^3.0.0` を追加
    - `flutter pub get` でパッケージ取得を確認
    - _Requirements: 2.1, 3.1_

  - [x] 1.2 Androidプラットフォーム権限設定
    - `frontend/android/app/src/main/AndroidManifest.xml` に `ACCESS_FINE_LOCATION` と `ACCESS_COARSE_LOCATION` パーミッションを追加
    - _Requirements: 1.1, 1.2_

  - [x] 1.3 iOSプラットフォーム権限設定
    - `frontend/ios/Runner/Info.plist` に `NSLocationWhenInUseUsageDescription` キーを追加
    - 使用理由: 「現在地からお住まいの地域を自動設定するために位置情報を使用します。」
    - _Requirements: 1.1, 1.2_

- [x] 2. データモデルとエラーモデルの実装
  - [x] 2.1 位置情報関連モデルクラスの作成
    - `frontend/lib/models/location.dart` を新規作成
    - `GeoPosition` クラス（latitude, longitude）
    - `GeoAddress` クラス（country, administrativeArea, locality）
    - `RegionMatchResult` クラス（prefecture, municipality）
    - _Requirements: 2.1, 3.1, 4.1_

  - [x] 2.2 エラーモデルの作成
    - `frontend/lib/models/location_error.dart` を新規作成
    - `LocationErrorType` enum（serviceDisabled, permissionDenied, permissionDeniedForever, gpsTimeout, gpsUnavailable, geocodingTimeout, geocodingFailed, outsideJapan, addressIncomplete, prefectureNotFound, municipalityNotFound）
    - `LocationError` クラス（type, userMessage, canRetry, showSettings）
    - `LocationError.fromType` ファクトリメソッド（設計書のエラー対応表に基づく全メッセージ定義）
    - `LocationException` 例外クラス
    - _Requirements: 1.4, 1.5, 1.6, 2.4, 2.5, 3.3, 3.4, 3.5, 4.3, 4.4, 7.1, 7.2, 7.3_

- [x] 3. LocationServiceの実装
  - [x] 3.1 LocationServiceクラスの作成
    - `frontend/lib/services/location_service.dart` を新規作成
    - コンストラクタでRegionServiceをDI
    - `checkPermission()`: geolocatorを使った権限状態確認
    - `requestPermission()`: 権限リクエスト処理
    - `isLocationServiceEnabled()`: 位置情報サービスの有効確認
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 3.2 GPS位置情報取得メソッドの実装
    - `getCurrentPosition()`: geolocator経由でGPS座標取得（タイムアウト10秒）
    - タイムアウト時は `LocationException(type: gpsTimeout)` をスロー
    - GPS信号取得不可時は `LocationException(type: gpsUnavailable)` をスロー
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

  - [x] 3.3 逆ジオコーディングメソッドの実装
    - `reverseGeocode(latitude, longitude)`: geocodingパッケージで住所情報取得（タイムアウト5秒）
    - 日本国外判定: countryが「日本」「Japan」「JP」以外なら `outsideJapan` エラー
    - 住所情報不完全（都道府県名/市区町村名がnull）なら `addressIncomplete` エラー
    - タイムアウト時は `geocodingTimeout` エラー
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.4 地域マッチングメソッドの実装
    - `matchRegion(GeoAddress address)`: 逆ジオコーディング結果とアプリ内JSONデータの照合
    - 都道府県: `administrativeArea` と `prefectures.json` の `name` を完全一致比較
    - 市区町村: `locality` と `municipalities.json` の `name` を前方一致比較
    - マッチ失敗時は `prefectureNotFound` / `municipalityNotFound` エラー
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.5 一連処理を統合する detectRegion メソッドの実装
    - `detectRegion()`: 権限確認 → GPS取得 → 逆ジオコーディング → マッチング を順次実行
    - 各ステップのエラーを適切にスローしフォールバックを実現
    - _Requirements: 5.2, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 3.6 LocationServiceのユニットテスト
    - `test/unit/services/location_service_test.dart` を新規作成
    - 各権限状態での分岐テスト（許可、拒否、永続的拒否、サービス無効）
    - GPS取得の正常系・タイムアウト・信号不可テスト
    - 逆ジオコーディングの正常系・タイムアウト・日本国外・住所不完全テスト
    - マッチングの正常系・都道府県不一致・市区町村不一致テスト
    - geolocator/geocodingのプラットフォーム依存部分をモック化
    - _Requirements: 1.1-1.6, 2.1-2.5, 3.1-3.5, 4.1-4.5_

  - [ ]* 3.7 プロパティテスト: 日本国外住所の拒否（Property 1）
    - `test/unit/services/location_service_property_test.dart` を新規作成
    - **Property 1: 日本国外住所の拒否**
    - gladosで任意のGeoAddressを生成し、countryが「日本」「Japan」「JP」以外の場合に `outsideJapan` エラーが返されることを検証
    - countryが日本を示す場合は住所検証処理が続行されることを検証
    - **Validates: Requirements 3.3**

  - [ ]* 3.8 プロパティテスト: 地域マッチングの正確性（Property 2）
    - **Property 2: 地域マッチングの正確性**
    - gladosで任意の都道府県名・市区町村名ペアを生成し:
      - アプリ内データと完全一致/前方一致する場合に正しいRegionMatchResultが返ることを検証
      - 都道府県名が不一致の場合に `prefectureNotFound` エラーを検証
      - 市区町村名が前方一致しない場合に `municipalityNotFound` エラーを検証
    - **Validates: Requirements 4.2, 4.3, 4.4**

- [x] 4. チェックポイント - サービス層の確認
  - すべてのテストが通ることを確認し、問題があればユーザーに質問する。

- [x] 5. LocationProvider（状態管理層）の実装
  - [x] 5.1 LocationDetectionState と LocationDetectionNotifier の作成
    - `frontend/lib/providers/location_provider.dart` を新規作成
    - `LocationDetectionPhase` enum（idle, checkingPermission, acquiringLocation, geocoding, matching, success, error）
    - `LocationDetectionState` クラス（phase, result, error, message, isLoading getter）
    - `LocationDetectionNotifier` extends StateNotifier（LocationServiceをDI）
    - `detectRegion()`: 各フェーズで状態を更新しながらLocationServiceを呼び出す
    - `reset()`: idle状態にリセット
    - _Requirements: 2.2, 5.2, 5.5_

  - [x] 5.2 Riverpod Provider定義の追加
    - `locationServiceProvider`: LocationServiceのProvider（RegionServiceをDI）
    - `locationDetectionProvider`: StateNotifierProvider<LocationDetectionNotifier, LocationDetectionState>
    - _Requirements: 5.2, 5.5_

  - [ ]* 5.3 LocationDetectionNotifierのユニットテスト
    - `test/unit/providers/location_provider_test.dart` を新規作成
    - 正常フロー: idle → checkingPermission → acquiringLocation → geocoding → matching → success の状態遷移を検証
    - エラーフロー: 各フェーズでエラー発生時に error 状態に遷移し、適切なLocationErrorが設定されることを検証
    - reset()呼び出し後にidle状態に戻ることを検証
    - _Requirements: 5.2, 5.5, 7.1, 7.2, 7.3_

  - [ ]* 5.4 プロパティテスト: エラー時のフォールバック保証（Property 3）
    - **Property 3: エラー時のフォールバック保証**
    - gladosで任意のLocationErrorTypeを生成し、エラー発生後もLocationDetectionStateがerrorに遷移するのみで、既存の手動選択状態（RegionSettingProvider）に影響を与えないことを検証
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

- [x] 6. 地域選択画面へのGPS_Button追加
  - [x] 6.1 GPS_Buttonウィジェットの実装
    - `frontend/lib/widgets/gps_button.dart` を新規作成
    - GPSアイコン + 「現在地から設定」テキストの ElevatedButton
    - ローディング中は CircularProgressIndicator を表示し非活性化
    - エラー時はエラーメッセージ表示エリア（canRetryならリトライボタン、showSettingsなら設定遷移ボタン）
    - 成功時は「現在地から検出しました」確認メッセージを2秒間表示
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 7.5_

  - [x] 6.2 RegionSelectionScreenへのGPS_Button統合
    - `frontend/lib/screens/region_selection_screen.dart` を更新
    - 説明文（`_buildDescription`）の下にGPS_Buttonを配置
    - locationDetectionProviderをwatchし、成功時に都道府県・市区町村を自動選択状態に設定
    - 成功時に地区選択カードをアクティブ化（ステッパーのステップ3へ遷移）
    - GPS処理中も既存の手動選択UIは独立して動作可能な状態を維持
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.4_

  - [ ]* 6.3 GPS_Buttonのウィジェットテスト
    - `test/widget/gps_button_test.dart` を新規作成
    - ボタン表示の確認（GPSアイコン + テキスト）
    - ローディング状態でのインジケーター表示とボタン非活性を確認
    - エラー状態でのメッセージ表示とリトライボタンを確認
    - 成功状態での確認メッセージ表示を確認
    - _Requirements: 5.1, 5.5_

- [x] 7. 設定画面への「現在地から再設定」ボタン追加
  - [x] 7.1 SettingsScreenへの再設定ボタン追加
    - `frontend/lib/screens/settings_screen.dart` を更新
    - 「地域設定」セクション内に「現在地から再設定」ボタンを追加（GPSアイコン付き）
    - ボタン押下時に地域選択画面へ遷移し、GPS検出を自動開始するパラメータを渡す
    - _Requirements: 6.1, 6.2_

  - [x] 7.2 RegionSelectionScreenへのautoDetectパラメータ追加
    - `frontend/lib/screens/region_selection_screen.dart` を更新
    - コンストラクタに `autoDetect` パラメータ（bool、デフォルトfalse）を追加
    - `autoDetect: true` の場合、画面表示時（initState）に自動的にdetectRegion()を実行
    - 地域マッチング成功時は都道府県・市区町村を選択済み状態で表示、地区選択をアクティブ化
    - 地区選択完了後に設定を保存し、設定画面に戻り「地域設定を更新しました」フィードバックを2秒間表示
    - 戻るボタン押下時は地域設定を変更せずに設定画面へ戻る
    - _Requirements: 6.2, 6.3, 6.4, 6.5_

  - [ ]* 7.3 設定画面の統合ウィジェットテスト
    - `test/widget/settings_gps_test.dart` を新規作成
    - 「現在地から再設定」ボタンの表示確認
    - ボタン押下で地域選択画面へ遷移することを確認
    - 戻るボタンで設定が変更されないことを確認
    - _Requirements: 6.1, 6.5_

- [x] 8. 最終チェックポイント - 全体統合確認
  - すべてのテストが通ることを確認し、問題があればユーザーに質問する。

## Notes

- タスクに `*` が付いているサブタスクはオプションであり、MVP優先時にはスキップ可能
- 各タスクは要件への参照を含み、トレーサビリティを確保
- チェックポイントでは段階的に動作検証を行う
- プロパティテストは既存の glados パッケージを使用
- ユニットテストは flutter_test を使用
- geolocator/geocoding のプラットフォーム依存部分はインターフェース経由でモック化してテスト
- 既存の手動地域選択機能を阻害しないフォールバック処理が最重要設計方針
- ファイルパスはすべて `frontend/` ディレクトリ基準

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3", "3.4"] },
    { "id": 3, "tasks": ["3.5"] },
    { "id": 4, "tasks": ["3.6", "3.7", "3.8"] },
    { "id": 5, "tasks": ["5.1", "5.2"] },
    { "id": 6, "tasks": ["5.3", "5.4"] },
    { "id": 7, "tasks": ["6.1"] },
    { "id": 8, "tasks": ["6.2", "7.1"] },
    { "id": 9, "tasks": ["7.2"] },
    { "id": 10, "tasks": ["6.3", "7.3"] }
  ]
}
```
