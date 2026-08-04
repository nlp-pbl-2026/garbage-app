# Implementation Plan: カレンダーメモ・天気機能

## Overview

カレンダー画面にメモ機能（CRUD + 永続化）と天気アイコンのDay_Cell表示を追加する。MemoServiceを新規実装し、Riverpodプロバイダー経由でUI層に接続する。既存のWeatherService/weatherForecastProviderを活用して天気アイコンをカレンダーセルに表示する。

## Tasks

- [x] 1. MemoServiceの実装
  - [x] 1.1 MemoServiceクラスを作成する
    - `lib/services/memo_service.dart` を新規作成
    - SharedPreferencesを使用したJSON形式の永続化ロジックを実装
    - `init()`, `getMemo(date)`, `getMemoDatesForMonth(year, month)`, `saveMemo(date, text)`, `deleteMemo(date)` メソッドを実装
    - `_dateToKey()`, `_serialize()`, `_deserialize()`, `isValidMemoText()` ヘルパーメソッドを実装
    - バリデーション: 空白文字列拒否、200文字上限
    - エラーハンドリング: SharedPreferences読み込み/書き込み失敗時の対処
    - _Requirements: 1.2, 1.3, 1.4, 2.2, 3.2, 7.1, 7.2, 7.3, 8.1_

  - [ ]* 1.2 MemoServiceのプロパティベーステストを作成する
    - `test/property/memo_service_property_test.dart` を新規作成
    - **Property 1: メモのシリアライズ・ラウンドトリップ**
    - **Property 2: 1日付1メモ（最終書き込み勝ち）**
    - **Property 3: 空白文字列の拒否**
    - **Property 4: メモ削除後の不在**
    - **Property 5: 文字数制限バリデーション**
    - **Validates: Requirements 1.2, 1.3, 1.4, 2.2, 3.2, 7.1, 7.2, 7.3, 8.1**

  - [ ]* 1.3 MemoServiceのユニットテストを作成する
    - `test/unit/memo_service_test.dart` を新規作成
    - メモ保存・取得・削除の具体的シナリオ
    - 境界値テスト（200文字ちょうど、201文字、空文字、空白のみ）
    - JSON永続化の正常系・異常系
    - _Requirements: 1.2, 1.3, 1.4, 2.2, 3.2, 7.1, 7.2, 7.3, 8.1, 8.2_

- [x] 2. Memo Riverpodプロバイダーの実装
  - [x] 2.1 メモ用プロバイダーを作成する
    - `lib/providers/memo_provider.dart` を新規作成
    - `memoServiceProvider`: MemoServiceインスタンスを提供
    - `monthlyMemosProvider`: 月ごとのメモ日付セットを提供（family provider）
    - `memoForDateProvider`: 特定日付のメモテキストを提供（family provider）
    - MemoServiceの初期化をアプリ起動フローに組み込む
    - _Requirements: 4.1, 4.3, 7.2_

  - [ ]* 2.2 メモプロバイダーのユニットテストを作成する
    - `test/unit/memo_provider_test.dart` を新規作成
    - プロバイダー状態管理の正常系テスト
    - _Requirements: 4.1, 4.3, 7.2_

- [x] 3. Checkpoint - MemoServiceとプロバイダーの確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. MemoDialogウィジェットの実装
  - [x] 4.1 メモ入力ダイアログを作成する
    - `lib/widgets/memo_dialog.dart` を新規作成
    - ConsumerStatefulWidgetとして実装
    - テキスト入力フィールド（maxLength: 200、TextInputFormatterで制限）
    - 文字数カウンター表示（現在の入力文字数 / 200）
    - 保存ボタン: 入力テキストでMemoServiceのsaveMemoを呼び出し
    - キャンセルボタン: ダイアログを閉じる
    - 削除ボタン: 既存メモ編集時のみ表示、確認ダイアログを経由して削除
    - 既存メモがある場合は入力欄にプリセット
    - 空テキストで保存押下時はダイアログを閉じるのみ
    - エラー時はSnackBarでメッセージ表示
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 3.1, 3.2, 8.1, 8.2, 8.3_

  - [ ]* 4.2 MemoDialogのウィジェットテストを作成する
    - `test/widget/memo_dialog_test.dart` を新規作成
    - ダイアログ表示・入力・保存フロー
    - 文字数カウンターの表示
    - 削除確認ダイアログの表示
    - _Requirements: 1.1, 1.4, 2.1, 3.1, 8.3_

- [x] 5. CalendarScreenへのメモ機能統合
  - [x] 5.1 カレンダー日付セルにメモアイコンインジケーターを追加する
    - `lib/screens/calendar_screen.dart` を修正
    - markerBuilder内でmemoプロバイダーを参照し、メモが存在する日付にアイコンを表示
    - メモアイコンはセル右上隅に小さなドット（4x4 px程度）で配置
    - ゴミカテゴリドットや天気アイコンと重ならないレイアウト
    - 月変更時にメモインジケーター状態を再読み込み
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 5.2 日付選択時のメモダイアログ起動を統合する
    - `lib/screens/calendar_screen.dart` を修正
    - 日付を長押し（またはメモアイコンタップ）でMemoDialogを表示
    - 既存メモがある場合は編集モードで開く
    - メモ保存/削除後にカレンダーのインジケーター状態を更新
    - _Requirements: 1.1, 2.1, 3.3_

- [x] 6. 天気アイコンのDay_Cell表示改善
  - [x] 6.1 天気詳細表示セクションを選択日情報に統合する
    - `lib/screens/calendar_screen.dart` の `_buildSelectedDaySchedule` を確認
    - 既存の天気情報表示が天気アイコン、天気名称、最高/最低気温、降水確率を含むか確認し、不足があれば追加
    - 天気予報データのない日付では天気情報セクションを非表示にする（既存ロジック確認）
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2_

- [x] 7. アプリ起動時のMemoService初期化
  - [x] 7.1 MemoServiceの初期化をmain.dartに組み込む
    - `lib/main.dart` を修正
    - アプリ起動時にSharedPreferencesからメモデータを読み込むよう初期化処理を追加
    - ProviderScopeのoverridesでMemoServiceインスタンスを設定
    - _Requirements: 7.2_

- [x] 8. Final checkpoint - 全機能の統合確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- 既存のWeatherService/weatherForecastProviderは変更不要（既に実装済み）
- テストはプロジェクトの既存ディレクトリ構造（test/property/, test/unit/, test/widget/）に従う
- プロパティベーステストにはプロジェクト既存のgladosパッケージを使用する

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "4.1", "7.1"] },
    { "id": 3, "tasks": ["4.2", "5.1", "5.2", "6.1"] }
  ]
}
```
