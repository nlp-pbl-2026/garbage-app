# Requirements Document

## Introduction

リアルタイムカメラプレビュー機能を追加する。本機能は、Flutter公式の`camera`パッケージを使用してデバイスカメラのライブプレビューを全画面表示する画面を提供する。将来的にはリアルタイムでゴミの判別を行う予定だが、本フェーズでは判別機能は含まず、カメラプレビューとプレースホルダーUIのみを実装する。既存のimage_input画面（静止画撮影用）とは別の専用画面として構築する。

## Glossary

- **Realtime_Camera_Screen**: カメラのライブプレビューを全画面表示する専用画面ウィジェット
- **Camera_Controller**: Flutter `camera`パッケージの`CameraController`を管理し、カメラの初期化・プレビュー表示・ライフサイクル制御を行うコンポーネント
- **Classification_Overlay**: 将来の判別結果表示用のプレースホルダーオーバーレイUI
- **Camera_Permission_Handler**: カメラ権限のリクエストと状態管理を行うコンポーネント
- **Image_Input_Screen**: 既存の静止画撮影・ギャラリー選択によるアップロード画面

## Requirements

### Requirement 1: カメラプレビュー表示

**User Story:** As a ユーザー, I want デバイスカメラのリアルタイムプレビューを全画面で確認できること, so that 将来実装される判別機能を利用するための基盤画面として使用できる。

#### Acceptance Criteria

1. WHEN Realtime_Camera_Screenが表示された時, THE Camera_Controller SHALL デバイスの背面カメラを初期化しライブプレビューを開始する
2. WHILE カメラが正常に初期化されている状態, THE Realtime_Camera_Screen SHALL カメラプレビューを画面全体に表示する
3. WHEN カメラの初期化が完了する前, THE Realtime_Camera_Screen SHALL ローディングインジケーターを表示する

### Requirement 2: カメラ権限管理

**User Story:** As a ユーザー, I want カメラ権限の許可を求められた際に適切なガイダンスを受けたい, so that スムーズにカメラ機能を利用開始できる。

#### Acceptance Criteria

1. WHEN Realtime_Camera_Screenへの遷移が開始された時, THE Camera_Permission_Handler SHALL カメラ権限の状態を確認する
2. WHEN カメラ権限が未許可の場合, THE Camera_Permission_Handler SHALL ユーザーにカメラ権限の許可をリクエストする
3. WHEN カメラ権限が許可された場合, THE Camera_Controller SHALL カメラの初期化を開始する
4. IF カメラ権限が拒否された場合, THEN THE Realtime_Camera_Screen SHALL 権限が必要である旨のメッセージと設定画面への誘導ボタンを表示する
5. IF カメラ権限が永久に拒否された場合, THEN THE Realtime_Camera_Screen SHALL デバイスの設定アプリへの誘導メッセージを表示する

### Requirement 3: 判別結果プレースホルダー表示

**User Story:** As a 開発者, I want 将来の判別結果表示エリアをプレースホルダーとして配置したい, so that 判別機能実装時にUIの追加変更を最小限に抑えられる。

#### Acceptance Criteria

1. WHILE カメラプレビューが表示されている状態, THE Classification_Overlay SHALL プレビュー上にオーバーレイとして判別結果プレースホルダーを表示する
2. THE Classification_Overlay SHALL 「判別結果がここに表示されます」というテキストをプレースホルダーとして表示する
3. THE Classification_Overlay SHALL カメラプレビューの視認性を妨げない半透明のデザインで表示する

### Requirement 4: 画面遷移

**User Story:** As a ユーザー, I want 画像入力画面からリアルタイムカメラ画面に簡単に移動したい, so that 用途に応じて静止画撮影とリアルタイムプレビューを使い分けられる。

#### Acceptance Criteria

1. WHILE Image_Input_Screenが初期状態で表示されている時, THE Image_Input_Screen SHALL Realtime_Camera_Screenへ遷移するためのボタンを表示する
2. WHEN ユーザーがリアルタイムカメラボタンをタップした時, THE Image_Input_Screen SHALL Realtime_Camera_Screenへ画面遷移する
3. WHILE Realtime_Camera_Screenが表示されている時, THE Realtime_Camera_Screen SHALL 前の画面に戻るためのボタンを表示する
4. WHEN ユーザーが戻るボタンをタップした時, THE Realtime_Camera_Screen SHALL 前の画面へ戻る

### Requirement 5: カメラライフサイクル管理

**User Story:** As a 開発者, I want カメラリソースが適切に管理されること, so that バッテリー消費を抑え、他アプリのカメラ利用を妨げない。

#### Acceptance Criteria

1. WHEN Realtime_Camera_Screenが非表示になった時（画面遷移やアプリバックグラウンド化）, THE Camera_Controller SHALL カメラプレビューを一時停止しリソースを解放する
2. WHEN Realtime_Camera_Screenが再度表示された時（画面復帰やアプリフォアグラウンド化）, THE Camera_Controller SHALL カメラプレビューを再開する
3. WHEN Realtime_Camera_Screenが破棄された時, THE Camera_Controller SHALL カメラリソースを完全に解放する

### Requirement 6: エラーハンドリング

**User Story:** As a ユーザー, I want カメラが利用できない場合にエラーメッセージを確認できること, so that 問題の原因を理解し対処できる。

#### Acceptance Criteria

1. IF カメラの初期化に失敗した場合, THEN THE Realtime_Camera_Screen SHALL エラーメッセージを表示する
2. IF デバイスにカメラが搭載されていない場合, THEN THE Realtime_Camera_Screen SHALL カメラが利用できない旨のメッセージを表示する
3. IF カメラプレビュー中にエラーが発生した場合, THEN THE Realtime_Camera_Screen SHALL エラーメッセージと再試行ボタンを表示する
