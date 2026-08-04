# Requirements Document

## Introduction

画像入力機能を追加する。ユーザーがカメラ撮影またはギャラリーから画像を選択し、アプリに取り込むことができる。この機能はゴミ分類機能の前段階として、画像の取得・表示・バックエンドへのアップロードまでを対象とする。

## Glossary

- **Image_Input_Screen**: 画像を撮影またはギャラリーから選択するためのFlutter画面
- **Image_Picker**: カメラまたはギャラリーから画像を取得するFlutterコンポーネント
- **Image_Upload_API**: 画像ファイルを受け取り保存するFastAPIエンドポイント
- **Image_Preview**: 選択された画像をユーザーに表示するUIコンポーネント
- **Supported_Format**: JPEG、PNG形式の画像ファイル
- **Max_File_Size**: アップロード可能な画像の最大サイズ（10MB）

## Requirements

### Requirement 1: 画像入力方法の選択

**User Story:** As a ユーザー, I want カメラ撮影とギャラリーから画像入力方法を選択できること, so that 状況に応じて最適な方法で画像を取り込める

#### Acceptance Criteria

1. WHEN ユーザーが画像入力画面を開いたとき, THE Image_Input_Screen SHALL カメラ撮影ボタンとギャラリー選択ボタンの2つの入力方法を表示する
2. WHEN ユーザーがカメラ撮影ボタンを押したとき, THE Image_Picker SHALL デバイスのカメラを起動する
3. WHEN ユーザーがギャラリー選択ボタンを押したとき, THE Image_Picker SHALL デバイスのギャラリー（フォトライブラリ）を開く

### Requirement 2: カメラによる画像撮影

**User Story:** As a ユーザー, I want カメラで写真を撮影して画像を入力したい, so that その場で対象物を撮影できる

#### Acceptance Criteria

1. WHEN カメラが起動して撮影が完了したとき, THE Image_Picker SHALL 撮影した画像を Image_Preview に表示する
2. WHEN ユーザーがカメラ撮影をキャンセルしたとき, THE Image_Picker SHALL Image_Input_Screen に戻り、以前の状態を維持する
3. IF デバイスにカメラが搭載されていない場合, THEN THE Image_Input_Screen SHALL カメラ撮影ボタンを非活性にする

### Requirement 3: ギャラリーからの画像選択

**User Story:** As a ユーザー, I want ギャラリーから既存の画像を選択したい, so that 事前に撮影した画像を使用できる

#### Acceptance Criteria

1. WHEN ギャラリーで画像が選択されたとき, THE Image_Picker SHALL 選択された画像を Image_Preview に表示する
2. WHEN ユーザーがギャラリー選択をキャンセルしたとき, THE Image_Picker SHALL Image_Input_Screen に戻り、以前の状態を維持する

### Requirement 4: 画像プレビューと確認

**User Story:** As a ユーザー, I want 選択した画像をプレビューで確認してから送信したい, so that 意図した画像であることを確認できる

#### Acceptance Criteria

1. WHEN 画像が選択またはキャプチャされたとき, THE Image_Preview SHALL 選択された画像を画面上に表示する
2. WHILE 画像が Image_Preview に表示されている状態で, THE Image_Input_Screen SHALL 「送信」ボタンと「やり直し」ボタンを表示する
3. WHEN ユーザーが「やり直し」ボタンを押したとき, THE Image_Input_Screen SHALL 画像プレビューをクリアし、画像入力方法の選択状態に戻る

### Requirement 5: 画像のバリデーション

**User Story:** As a ユーザー, I want 不正な画像がアップロードされないようにしたい, so that システムが正常に動作する

#### Acceptance Criteria

1. WHEN 画像が選択されたとき, THE Image_Picker SHALL 画像が Supported_Format（JPEGまたはPNG）であることを検証する
2. WHEN 画像が選択されたとき, THE Image_Picker SHALL 画像のファイルサイズが Max_File_Size（10MB）以下であることを検証する
3. IF 画像が Supported_Format でない場合, THEN THE Image_Input_Screen SHALL 「JPEG または PNG 形式の画像を選択してください」というエラーメッセージを表示する
4. IF 画像のファイルサイズが Max_File_Size を超えている場合, THEN THE Image_Input_Screen SHALL 「画像サイズは10MB以下にしてください」というエラーメッセージを表示する

### Requirement 6: 画像のアップロード

**User Story:** As a ユーザー, I want 選択した画像をサーバーにアップロードしたい, so that 後でゴミ分類機能で利用できる

#### Acceptance Criteria

1. WHEN ユーザーが「送信」ボタンを押したとき, THE Image_Input_Screen SHALL 画像を Image_Upload_API にアップロードする
2. WHILE アップロードが処理中のとき, THE Image_Input_Screen SHALL ローディングインジケーターを表示し、「送信」ボタンを非活性にする
3. WHEN アップロードが成功したとき, THE Image_Input_Screen SHALL 成功メッセージを表示し、画像入力方法の選択状態にリセットする
4. IF アップロードが失敗した場合, THEN THE Image_Input_Screen SHALL エラーメッセージを表示し、画像プレビューを維持して再送信を可能にする

### Requirement 7: バックエンドの画像受信

**User Story:** As a システム管理者, I want サーバーで画像を受信・保存したい, so that 後続処理で画像を利用できる

#### Acceptance Criteria

1. WHEN Image_Upload_API が画像ファイルを受信したとき, THE Image_Upload_API SHALL 画像をサーバーのストレージに保存し、画像IDを含むレスポンスを返す
2. WHEN Image_Upload_API が画像ファイルを受信したとき, THE Image_Upload_API SHALL 画像のメタデータ（ファイル名、サイズ、形式、アップロード日時）をデータベースに保存する
3. IF 受信した画像が Supported_Format でない場合, THEN THE Image_Upload_API SHALL HTTPステータス400とエラーメッセージを返す
4. IF 受信した画像のファイルサイズが Max_File_Size を超えている場合, THEN THE Image_Upload_API SHALL HTTPステータス413とエラーメッセージを返す

### Requirement 8: パーミッション管理

**User Story:** As a ユーザー, I want アプリがカメラやストレージのパーミッションを適切にリクエストしてほしい, so that プライバシーを保ちながら機能を利用できる

#### Acceptance Criteria

1. WHEN ユーザーが初めてカメラ撮影ボタンを押したとき, THE Image_Picker SHALL カメラパーミッションをリクエストする
2. WHEN ユーザーが初めてギャラリー選択ボタンを押したとき, THE Image_Picker SHALL フォトライブラリアクセスのパーミッションをリクエストする
3. IF ユーザーがカメラパーミッションを拒否した場合, THEN THE Image_Input_Screen SHALL 「カメラのアクセス許可が必要です。設定から許可してください」というメッセージを表示する
4. IF ユーザーがフォトライブラリアクセスのパーミッションを拒否した場合, THEN THE Image_Input_Screen SHALL 「写真へのアクセス許可が必要です。設定から許可してください」というメッセージを表示する
