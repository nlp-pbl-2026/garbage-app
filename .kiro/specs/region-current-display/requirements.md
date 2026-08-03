# Requirements Document

## Introduction

地域選択画面（RegionSelectionScreen）を開いた際に、既に保存済みの地域設定（都道府県・市区町村・地区）を画面上に表示する機能。ユーザーが現在の設定を視覚的に確認でき、変更時にどこからどこへ変えるのかが明確になることで、操作性を向上させる。

## Glossary

- **Region_Selection_Screen**: 3段階ステッパー形式（都道府県→市区町村→地区）で地域を選択するFlutter画面ウィジェット
- **Region_Setting**: SharedPreferencesに保存される地域設定データ（prefectureId, prefectureName, municipalityId, municipalityName, districtId, districtName を保持）
- **Region_Setting_Provider**: regionSettingProviderとして実装された、Region_Settingの読み込み・保存を管理するRiverpod StateNotifierProvider
- **Current_Setting_Banner**: 地域選択画面の上部に表示される、現在の地域設定を示すUI要素
- **Step_Card**: 都道府県・市区町村・地区の各選択ステップを表すカード形式のUIコンポーネント
- **Initial_Setup_Mode**: Region_Settingが未設定（null）の状態で地域選択画面が表示されるモード
- **Change_Mode**: Region_Settingが設定済みの状態で地域選択画面が表示されるモード（設定変更時）

## Requirements

### Requirement 1: 現在の地域設定バナー表示

**User Story:** As a ユーザー, I want to 地域選択画面を開いたときに現在の地域設定を確認したい, so that 何が設定されているか把握した上で変更操作を行える。

#### Acceptance Criteria

1. WHILE Region_Setting が保存済みである（Change_Mode）, THE Region_Selection_Screen SHALL 画面上部のヘッダー直下に Current_Setting_Banner を表示する
2. THE Current_Setting_Banner SHALL 「現在の設定: {prefectureName} {municipalityName} {districtName}」の形式で現在の地域設定を表示する
3. WHILE Region_Setting が未設定である（Initial_Setup_Mode）, THE Region_Selection_Screen SHALL Current_Setting_Banner を非表示にする
4. WHEN Region_Selection_Screen が表示される, THE Region_Setting_Provider SHALL SharedPreferences から保存済みの Region_Setting を読み込み Current_Setting_Banner に反映する

### Requirement 2: 設定済みの値をステップカードにプリセット表示

**User Story:** As a ユーザー, I want to 地域選択画面を開いたときに各ステップカードに現在の設定値がプリセットされて表示されたい, so that 変更したい部分だけを選び直すことができる。

#### Acceptance Criteria

1. WHEN Region_Selection_Screen が Change_Mode で表示される, THE Region_Selection_Screen SHALL 保存済みの Region_Setting の prefectureName を都道府県 Step_Card に選択済み状態で表示する
2. WHEN Region_Selection_Screen が Change_Mode で表示される, THE Region_Selection_Screen SHALL 保存済みの Region_Setting の municipalityName を市区町村 Step_Card に選択済み状態で表示する
3. WHEN Region_Selection_Screen が Change_Mode で表示される, THE Region_Selection_Screen SHALL 保存済みの Region_Setting の districtName を地区 Step_Card に選択済み状態で表示する
4. WHEN Region_Selection_Screen が Change_Mode で表示される, THE Region_Selection_Screen SHALL 市区町村 Step_Card と地区 Step_Card をアクティブ状態（タップ可能）で表示する
5. WHILE Initial_Setup_Mode である, THE Region_Selection_Screen SHALL 全ての Step_Card を未選択状態で表示する（従来の動作を維持する）

### Requirement 3: プリセット値からの部分変更

**User Story:** As a ユーザー, I want to プリセットされた地域設定の一部だけを変更したい, so that 全て最初から選び直す手間が省ける。

#### Acceptance Criteria

1. WHEN ユーザーが都道府県 Step_Card で新しい都道府県を選択する, THE Region_Selection_Screen SHALL 市区町村 Step_Card と地区 Step_Card の選択値をリセットする（従来の動作を維持する）
2. WHEN ユーザーが市区町村 Step_Card で新しい市区町村を選択する, THE Region_Selection_Screen SHALL 地区 Step_Card の選択値をリセットする（従来の動作を維持する）
3. WHEN ユーザーが地区 Step_Card で新しい地区を選択する, THE Region_Selection_Screen SHALL 都道府県と市区町村の選択状態を維持する

### Requirement 4: プリセット時のデータ整合性

**User Story:** As a ユーザー, I want to プリセットされた値が正確に反映されてほしい, so that 誤った設定で保存してしまうことを防ぎたい。

#### Acceptance Criteria

1. WHEN Region_Selection_Screen が Change_Mode で表示される, THE Region_Selection_Screen SHALL Region_Setting の prefectureId を使用して市区町村一覧の取得を可能にする（municipalitiesProvider に正しいID が渡される）
2. WHEN Region_Selection_Screen が Change_Mode で表示される, THE Region_Selection_Screen SHALL Region_Setting の municipalityId を使用して地区一覧の取得を可能にする（districtsProvider に正しいID が渡される）
3. IF Region_Setting の読み込みに失敗する, THEN THE Region_Selection_Screen SHALL Initial_Setup_Mode と同じ動作（全て未選択状態）にフォールバックする
