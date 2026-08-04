# Implementation Plan: Realtime Camera

## Overview

リアルタイムカメラプレビュー機能の実装。Flutter `camera` パッケージを使用したライブプレビュー画面を構築し、CameraService による抽象化、Riverpod StateNotifier による状態管理、WidgetsBindingObserver によるライフサイクル管理を行う。既存の ImageInputScreen にナビゲーションボタンを追加して接続する。

## Tasks

- [x] 1. 依存パッケージ追加とサービス層の構築
  - [x] 1.1 `camera` パッケージを追加し CameraService を実装する
    - `pubspec.yaml` に `camera` パッケージを追加
    - `lib/services/camera_service.dart` を作成
    - `getAvailableCameras()` — 利用可能なカメラ一覧を取得
    - `createController(CameraDescription, ResolutionPreset)` — コントローラー生成
    - `initializeController(CameraController)` — 初期化
    - `pausePreview(CameraController)` / `resumePreview(CameraController)` — プレビュー制御
    - `disposeController(CameraController)` — リソース解放
    - テスト時にモック可能な設計（Riverpod Provider で提供）
    - _Requirements: 1.1, 5.1, 5.2, 5.3_

- [x] 2. 状態管理の構築
  - [x] 2.1 RealtimeCameraState と RealtimeCameraNotifier を実装する
    - `lib/providers/realtime_camera_provider.dart` を作成
    - `RealtimeCameraStatus` enum を定義（loading, previewing, permissionDenied, permissionPermanentlyDenied, error, noCameraAvailable）
    - `RealtimeCameraState` クラスを定義（status, controller, errorMessage）
    - `RealtimeCameraNotifier` を実装:
      - `initialize()` — 権限確認 → カメラ初期化 → previewing 遷移
      - `retry()` — エラー時の再初期化
      - `onLifecycleChanged(AppLifecycleState)` — ライフサイクル連動
      - `dispose()` — リソース完全解放
    - `permission_handler` でカメラ権限をリクエスト・状態確認
    - 権限拒否 → permissionDenied、永久拒否 → permissionPermanentlyDenied
    - カメラなし → noCameraAvailable
    - 初期化失敗/ランタイムエラー → error（errorMessage 付き）
    - `realtimeCameraProvider` を StateNotifierProvider として定義
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3_

  - [ ]* 2.2 Property test: State machine happy path transitions を書く
    - **Property 1: State machine happy path transitions**
    - テストファイル `test/unit/realtime_camera_notifier_property_test.dart` を作成
    - `glados` を使用し、CameraService をモック
    - 権限 granted かつカメラ利用可能な場合、loading → previewing に遷移し controller が非 null であることを検証
    - 最小 100 イテレーション
    - **Validates: Requirements 1.1, 2.3**

  - [ ]* 2.3 Property test: Lifecycle round-trip restores camera を書く
    - **Property 2: Lifecycle round-trip restores camera**
    - テストファイル `test/unit/realtime_camera_notifier_property_test.dart` に追加
    - previewing 状態から非 resumed ライフサイクル → resumed で previewing に復帰することを検証
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 2.4 Property test: Non-resumed lifecycle releases resources を書く
    - **Property 3: Non-resumed lifecycle releases resources**
    - テストファイル `test/unit/realtime_camera_notifier_property_test.dart` に追加
    - 非 resumed 状態（paused, inactive, detached, hidden）受信時にリソースが解放されることを検証
    - **Validates: Requirements 5.1**

  - [ ]* 2.5 Property test: Error state transition on failure を書く
    - **Property 4: Error state transition on failure**
    - テストファイル `test/unit/realtime_camera_notifier_property_test.dart` に追加
    - 任意のエラー発生時に error 状態に遷移し errorMessage が非 null であることを検証
    - **Validates: Requirements 6.1, 6.3**

- [x] 3. Checkpoint - サービス層・状態管理確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. UI 層の構築
  - [x] 4.1 ClassificationOverlay ウィジェットを実装する
    - `lib/widgets/classification_overlay.dart` を作成
    - カメラプレビュー上に半透明オーバーレイとして表示
    - 「判別結果がここに表示されます」プレースホルダーテキストを表示
    - カメラプレビューの視認性を妨げないデザイン
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 4.2 RealtimeCameraScreen を実装する
    - `lib/screens/realtime_camera_screen.dart` を作成
    - ConsumerStatefulWidget + WidgetsBindingObserver を実装
    - `didChangeAppLifecycleState` で Notifier に通知
    - 状態に応じた UI 描画:
      - loading → CircularProgressIndicator
      - previewing → CameraPreview + ClassificationOverlay
      - permissionDenied → メッセージ + 設定画面誘導ボタン
      - permissionPermanentlyDenied → デバイス設定への誘導メッセージ
      - noCameraAvailable → カメラ利用不可メッセージ
      - error → エラーメッセージ + 再試行ボタン
    - 戻るボタン（AppBar または SafeArea 内のバックボタン）
    - _Requirements: 1.1, 1.2, 1.3, 2.4, 2.5, 4.3, 4.4, 6.1, 6.2, 6.3_

  - [x] 4.3 ImageInputScreen にリアルタイムカメラボタンを追加する
    - 既存の `lib/screens/image_input_screen.dart` の `_buildInitialState` メソッドを修正
    - 「リアルタイムカメラ」ボタンを追加
    - タップ時に `Navigator.push` で RealtimeCameraScreen へ遷移
    - _Requirements: 4.1, 4.2_

  - [ ]* 4.4 RealtimeCameraScreen のウィジェットテストを書く
    - テストファイル `test/widget/realtime_camera_screen_test.dart` を作成
    - loading 状態でローディングインジケーター表示を確認
    - permissionDenied 状態で権限メッセージ + 設定ボタン表示を確認
    - noCameraAvailable 状態でカメラ利用不可メッセージ表示を確認
    - error 状態でエラーメッセージ + 再試行ボタン表示を確認
    - 戻るボタンの表示を確認
    - _Requirements: 1.3, 2.4, 2.5, 4.3, 4.4, 6.1, 6.2, 6.3_

  - [ ]* 4.5 ClassificationOverlay のウィジェットテストを書く
    - テストファイル `test/widget/classification_overlay_test.dart` を作成
    - プレースホルダーテキスト「判別結果がここに表示されます」の表示を確認
    - 半透明デザインの検証
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Checkpoint - UI 層確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 結合とライフサイクル管理の検証
  - [x] 6.1 全コンポーネントを結合しナビゲーションフローを完成させる
    - ImageInputScreen → RealtimeCameraScreen の遷移が正常に動作することを確認
    - RealtimeCameraScreen の戻るボタンで前画面に戻ることを確認
    - WidgetsBindingObserver の登録・解除が initState/dispose で正しく行われることを確認
    - Notifier の dispose() で CameraController が確実に破棄されることを確認
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3_

  - [ ]* 6.2 RealtimeCameraNotifier のユニットテストを書く
    - テストファイル `test/unit/realtime_camera_notifier_test.dart` を作成
    - 権限許可 → initialize → previewing 遷移をテスト
    - 権限拒否 → permissionDenied 遷移をテスト
    - 権限永久拒否 → permissionPermanentlyDenied 遷移をテスト
    - カメラなし → noCameraAvailable 遷移をテスト
    - エラー → error 遷移 + errorMessage 確認
    - retry() で loading に戻ることをテスト
    - ライフサイクル paused → リソース解放をテスト
    - ライフサイクル resumed → 再初期化をテスト
    - dispose() で controller 破棄をテスト
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3_

- [x] 7. Final checkpoint - 全テスト確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (Properties 1-4 from design)
- Unit/widget tests validate specific scenarios and edge cases
- `glados` (already in dev_dependencies) is used for property-based tests
- `camera` package needs to be added to pubspec.yaml
- `permission_handler` is already in the project dependencies
- CameraService must be mockable for testing (use Riverpod Provider override)
- All UI text is in Japanese to match existing app conventions

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "6.1"] },
    { "id": 5, "tasks": ["6.2"] }
  ]
}
```
