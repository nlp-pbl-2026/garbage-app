# Requirements Document

## Introduction

ゴミ出しアプリの通知カスタマイズ機能。ユーザーがゴミ種別（可燃・資源・プラスチック・ペットボトル・危険）ごとに、前日通知と当日通知のON/OFFを個別に設定できる機能を提供する。設定はSharedPreferencesに永続化され、通知スケジューリング時にフィルタリングとして適用される。

## Glossary

- **NotificationCustomizationService**: ゴミ種別ごとの通知ON/OFF設定を管理するサービスコンポーネント
- **NotificationService**: flutter_local_notificationsを使用してローカル通知をスケジュールする既存サービス
- **GarbageCategory**: ゴミ分類カテゴリ（burnable, recyclable, plastic, petBottle, hazardous）
- **CategoryNotificationSetting**: 各ゴミ種別に対する前日通知・当日通知のON/OFF状態を表すデータモデル
- **SettingsUI**: 設定画面内の通知カスタマイズUIコンポーネント
- **SharedPreferences**: 端末ローカルにKey-Value形式でデータを永続化するストレージ

## Requirements

### Requirement 1: 種別通知設定のデータモデルと永続化

**User Story:** ユーザーとして、ゴミ種別ごとに前日通知と当日通知のON/OFFを設定したい。設定はアプリを再起動しても保持されるようにしたい。

#### Acceptance Criteria

1. THE NotificationCustomizationService SHALL 各GarbageCategoryに対して前日通知ON/OFFと当日通知ON/OFFの2つの設定値を管理する
2. THE NotificationCustomizationService SHALL 設定値をSharedPreferencesに永続化する
3. WHEN アプリが初回起動された場合、THE NotificationCustomizationService SHALL 全GarbageCategoryの前日通知と当日通知をON（有効）として初期化する
4. WHEN 設定値が変更された場合、THE NotificationCustomizationService SHALL 変更を即座にSharedPreferencesへ保存する
5. WHEN アプリが再起動された場合、THE NotificationCustomizationService SHALL SharedPreferencesから保存済みの設定値を読み込む

### Requirement 2: 通知スケジューリングへのフィルタリング適用

**User Story:** ユーザーとして、OFFに設定したゴミ種別の通知を受け取りたくない。必要な種別の通知だけ受け取れるようにしたい。

#### Acceptance Criteria

1. WHEN NotificationServiceが前日通知をスケジュールする際、THE NotificationService SHALL 前日通知がOFFに設定されたGarbageCategoryの通知をスケジュールから除外する
2. WHEN NotificationServiceが当日通知をスケジュールする際、THE NotificationService SHALL 当日通知がOFFに設定されたGarbageCategoryの通知をスケジュールから除外する
3. WHEN ある日の全GarbageCategoryが該当通知タイミングでOFFに設定されている場合、THE NotificationService SHALL その日・そのタイミングの通知をスケジュールしない
4. WHEN 種別通知設定が変更された場合、THE NotificationService SHALL スケジュール済み通知を再計算して更新する
5. WHEN フィルタリング適用後に通知対象のGarbageCategoryが複数存在する場合、THE NotificationService SHALL 通知本文に有効なGarbageCategoryのラベルのみを含める

### Requirement 3: 設定UIの提供

**User Story:** ユーザーとして、設定画面からゴミ種別ごとの通知ON/OFFを簡単に切り替えたい。

#### Acceptance Criteria

1. WHILE リマインダー通知が有効な状態、THE SettingsUI SHALL 通知設定カード内に種別ごとの通知カスタマイズセクションを表示する
2. THE SettingsUI SHALL 各GarbageCategory（5種別）に対して前日通知と当日通知それぞれのトグルスイッチを表示する
3. THE SettingsUI SHALL 各GarbageCategoryの名称とカテゴリカラーを表示して視覚的に識別可能にする
4. WHEN ユーザーがトグルスイッチを操作した場合、THE SettingsUI SHALL 即座にUI状態を更新し設定を永続化する
5. WHILE リマインダー通知が無効な状態、THE SettingsUI SHALL 種別通知カスタマイズセクションを非表示にする

### Requirement 4: 状態管理

**User Story:** 開発者として、種別通知設定をriverpodで一元管理し、UIとサービスの整合性を保ちたい。

#### Acceptance Criteria

1. THE NotificationCustomizationService SHALL flutter_riverpodのStateNotifierProviderを通じて状態を公開する
2. WHEN 状態が変更された場合、THE NotificationCustomizationService SHALL 依存するすべてのUIウィジェットに変更を通知する
3. WHEN NotificationCustomizationServiceが初期化される場合、THE NotificationCustomizationService SHALL SharedPreferencesからの読み込みが完了するまでローディング状態を公開する
4. IF SharedPreferencesからの読み込みに失敗した場合、THEN THE NotificationCustomizationService SHALL エラー状態を公開しつつ全種別ON（デフォルト値）で動作する
