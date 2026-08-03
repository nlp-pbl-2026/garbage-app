# Implementation Plan: Image Input

## Overview

画像入力機能の実装。Flutter フロントエンドでカメラ/ギャラリーからの画像取得・プレビュー・バリデーションを行い、FastAPI バックエンドで画像アップロード受信・保存・メタデータ管理を行う。フロントエンドとバックエンドを並行して構築し、最後に結合する。

## Tasks

- [ ] 1. バックエンド：画像アップロード基盤の構築
  - [x] 1.1 UploadedImage モデルとスキーマを追加する
    - `app/models.py` に `UploadedImage` SQLAlchemy モデルを追加（id, user_id, filename, original_filename, file_size, content_type, storage_path, uploaded_at）
    - `app/schemas.py` に `ImageUploadResponse` と `ImageErrorResponse` Pydantic スキーマを追加
    - DB マイグレーション（テーブル作成）を反映する
    - _Requirements: 7.1, 7.2_

  - [-] 1.2 ImageValidator サービスを実装する
    - `app/services/image_validator.py` を作成
    - Content-Type チェック（image/jpeg, image/png のみ許可）
    - ファイルサイズチェック（10MB 上限）
    - 不正フォーマット時は HTTP 400、サイズ超過時は HTTP 413 を raise
    - _Requirements: 7.3, 7.4_

  - [ ]* 1.3 ImageValidator のプロパティテストを書く
    - **Property 4: サーバー側フォーマット拒否**
    - **Property 5: サーバー側サイズ拒否**
    - `hypothesis` を使い、任意の content_type とファイルサイズで検証
    - `pytest` + `hypothesis` でテストファイル `tests/test_image_validator_properties.py` を作成
    - **Validates: Requirements 7.3, 7.4**

  - [-] 1.4 FileStorageService を実装する
    - `app/services/file_storage.py` を作成
    - UUID ベースのファイル名生成で保存
    - `uploads/` ディレクトリへの非同期ファイル書き込み
    - ファイル削除メソッドも実装
    - _Requirements: 7.1_

  - [~] 1.5 ImageUploadRouter を実装する
    - `app/routers/image_router.py` を作成
    - `POST /api/images/upload` エンドポイント（multipart/form-data）
    - 認証チェック（`get_current_user` 依存）
    - ImageValidator → FileStorageService → DB メタデータ保存の順で処理
    - `ImageUploadResponse` を返却（id, filename, file_size, content_type, uploaded_at）
    - `app/main.py` にルーターを登録
    - _Requirements: 6.1, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 1.6 画像アップロード API の統合テストを書く
    - `httpx` の `AsyncClient` を使い正常系・異常系をテスト
    - 正常アップロード → 201 レスポンスと image_id 返却を確認
    - 非対応フォーマット → 400 を確認
    - サイズ超過 → 413 を確認
    - 未認証 → 401 を確認
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [~] 2. Checkpoint - バックエンド確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. フロントエンド：画像取得・バリデーション基盤の構築
  - [x] 3.1 依存パッケージを追加し、ImageValidationService を実装する
    - `pubspec.yaml` に `image_picker` と `permission_handler` を追加
    - `lib/services/image_validation_service.dart` を作成
    - ファイル拡張子チェック（jpg, jpeg, png、大文字小文字不問）
    - ファイルサイズチェック（10MB 以下）
    - `ImageValidationResult` (isValid, errorMessage) を返却
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 3.2 ImageValidationService のプロパティテストを書く
    - **Property 1: フォーマットバリデーション（フロントエンド）**
    - **Property 2: サイズバリデーション（フロントエンド）**
    - `glados` を使い、任意の拡張子・ファイルサイズで検証
    - テストファイル `test/services/image_validation_service_property_test.dart` を作成
    - **Validates: Requirements 5.1, 5.2**

  - [-] 3.3 ImagePickerService を実装する
    - `lib/services/image_picker_service.dart` を作成
    - `pickFromCamera()` / `pickFromGallery()` メソッド
    - `isCameraAvailable()` でカメラ搭載チェック
    - `image_picker` パッケージをラップ（テスト可能に）
    - _Requirements: 1.2, 1.3, 2.1, 2.2, 3.1, 3.2_

  - [~] 3.4 ImageUploadService を実装する
    - `lib/services/image_upload_service.dart` を作成
    - `upload(XFile imageFile, String authToken)` メソッド
    - Multipart POST リクエストを `http` パッケージで送信
    - `ImageUploadResponse`（imageId, filename）をパース
    - ネットワークエラー・サーバーエラーのハンドリング
    - _Requirements: 6.1, 6.4_

- [ ] 4. フロントエンド：状態管理と画面の構築
  - [~] 4.1 ImageInputProvider（StateNotifier）を実装する
    - `lib/providers/image_input_provider.dart` を作成
    - `ImageInputState`（status, selectedImage, errorMessage, uploadedImageId, hasCameraPermission, hasGalleryPermission, isCameraAvailable）
    - `ImageInputNotifier` に `pickFromCamera()`, `pickFromGallery()`, `uploadImage()`, `reset()` を実装
    - パーミッションリクエスト → 画像取得 → バリデーション → 状態更新のフロー
    - エラーハンドリング（パーミッション拒否、バリデーション失敗、アップロード失敗）
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 3.1, 3.2, 4.3, 5.3, 5.4, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 4.2 ImageInputNotifier のユニットテストを書く
    - 状態遷移テスト（initial → previewing → uploading → success）
    - キャンセル時の状態維持テスト
    - パーミッション拒否時のエラーメッセージテスト
    - バリデーション失敗時のエラー状態テスト
    - アップロード失敗時のリトライ可能状態テスト
    - _Requirements: 2.2, 3.2, 5.3, 5.4, 6.2, 6.3, 6.4, 8.3, 8.4_

  - [~] 4.3 ImageInputScreen（UI）を実装する
    - `lib/screens/image_input_screen.dart` を作成（ConsumerWidget）
    - 初期状態：カメラボタン + ギャラリーボタン表示
    - カメラ非搭載時：カメラボタン非活性
    - プレビュー状態：画像表示 + 送信ボタン + やり直しボタン
    - アップロード中：ローディングインジケーター + 送信ボタン非活性
    - 成功状態：成功メッセージ表示 → 自動リセット
    - エラー状態：エラーメッセージ + 再送信ボタン
    - _Requirements: 1.1, 2.3, 4.1, 4.2, 4.3, 5.3, 5.4, 6.2, 6.3, 6.4, 8.3, 8.4_

  - [ ]* 4.4 ImageInputScreen のウィジェットテストを書く
    - 初期状態で2つのボタンが表示されることを確認
    - プレビュー状態で画像と送信/やり直しボタンが表示されることを確認
    - アップロード中にローディングインジケーターが表示されることを確認
    - エラー状態でエラーメッセージが表示されることを確認
    - _Requirements: 1.1, 4.1, 4.2, 6.2_

- [~] 5. Checkpoint - フロントエンド確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. 結合とナビゲーション
  - [~] 6.1 フロントエンドからバックエンドへのアップロードを結合する
    - ImageUploadService の API ベース URL を設定に追加
    - 認証トークンの取得と受け渡しを実装（既存の認証プロバイダーと連携）
    - ImageInputScreen をアプリのナビゲーションに組み込む
    - _Requirements: 6.1, 6.3_

  - [ ]* 6.2 エンドツーエンドの統合テストを書く
    - モック HTTP サーバーを使用したアップロードフロー全体のテスト
    - 正常系：画像選択 → バリデーション → アップロード → 成功表示
    - 異常系：ネットワークエラー → エラー表示 → リトライ
    - _Requirements: 6.1, 6.3, 6.4_

- [~] 7. Final checkpoint - 全テスト確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (Properties 1-5 from design)
- Unit/widget tests validate specific scenarios and edge cases
- Backend uses `pytest` + `hypothesis` for property tests
- Frontend uses `glados` (already in dev_dependencies) for property tests
- `image_picker` and `permission_handler` packages need to be added to pubspec.yaml
- Backend already has `python-multipart` for file uploads

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "1.4", "3.2", "3.3"] },
    { "id": 2, "tasks": ["1.3", "1.5", "3.4"] },
    { "id": 3, "tasks": ["1.6", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3"] },
    { "id": 5, "tasks": ["4.4", "6.1"] },
    { "id": 6, "tasks": ["6.2"] }
  ]
}
```
