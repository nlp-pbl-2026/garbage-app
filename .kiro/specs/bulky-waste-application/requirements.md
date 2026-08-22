# Requirements Document

## Introduction

粗大ごみ申し込み連携機能は、愛媛県向けゴミ出しアプリケーションに粗大ごみ収集の情報提供・申し込みガイド機能を追加する。ユーザーが選択した市区町村に応じて、粗大ごみの対象品目一覧、手数料、申し込み手順を提示し、各自治体の公式申し込み窓口（Webフォームまたは電話番号）へ誘導する。自治体ごとに異なる手数料体系・申し込み方法に対応し、粗大ごみ収集の一連のフロー（品目確認→手数料確認→申し込み→処理券購入→排出）をユーザーがスムーズに完了できるよう支援する。

## Glossary

- **App**: 愛媛県向けゴミ出しアプリケーション（Flutter製フロントエンドとFastAPIバックエンド）
- **Bulky_Waste_Screen**: 粗大ごみ機能のメイン画面
- **Item_List_View**: 粗大ごみ対象品目の一覧表示コンポーネント
- **Fee_Display**: 品目ごとの手数料を表示するコンポーネント
- **Application_Guide**: 粗大ごみ申し込み手順のステップガイドコンポーネント
- **External_Link_Handler**: 外部Webフォームまたは電話発信への遷移を処理するコンポーネント
- **Municipality_Config**: 自治体ごとの粗大ごみ設定データ（手数料体系、申し込み方法、連絡先等）
- **Bulky_Waste_Item**: 粗大ごみとして収集対象となる品目のデータモデル
- **Application_Method**: 申し込み方法の種別（web_form、phone、both）
- **Fee_Structure**: 手数料体系（品目サイズ別、重量別、一律等）
- **Status_Tracker**: 申し込み状況追跡コンポーネント（対応自治体のみ）
- **Backend_API**: FastAPIバックエンドの粗大ごみ関連エンドポイント群
- **Region_Setting**: ユーザーが選択した現在の地域設定（既存機能）

## Requirements

### Requirement 1: 粗大ごみ画面への導線

**User Story:** ユーザーとして、アプリのメイン画面から粗大ごみ機能に簡単にアクセスしたい。粗大ごみの出し方がわからないときにすぐ情報を得られるようにするため。

#### Acceptance Criteria

1. THE App SHALL display a navigation entry point labeled "粗大ごみ" to Bulky_Waste_Screen that is visible on the main screen without scrolling or navigating away from the initially displayed content
2. WHEN a user taps the bulky waste navigation entry, THE App SHALL navigate to Bulky_Waste_Screen within 300 milliseconds
3. IF Region_Setting is null (no municipality is configured) WHEN the user taps the bulky waste navigation entry, THEN THE App SHALL navigate to the region selection screen and display a message indicating that municipality selection is required before showing bulky waste information
4. IF Region_Setting is already configured WHEN the user taps the bulky waste navigation entry, THEN THE App SHALL navigate directly to Bulky_Waste_Screen displaying information for the configured municipality

### Requirement 2: 自治体別粗大ごみ情報の表示

**User Story:** ユーザーとして、自分が住んでいる市区町村の粗大ごみに関する基本情報を確認したい。収集ルールや受付時間を事前に把握するため。

#### Acceptance Criteria

1. WHEN Bulky_Waste_Screen is opened, THE App SHALL display the bulky waste collection overview for the municipality specified in Region_Setting within 3 seconds of screen open
2. WHILE Municipality_Config data is available for the selected municipality, THE Bulky_Waste_Screen SHALL display the municipality name, collection frequency (e.g. collection day-of-week or interval), reception hours, and collection rules as defined in Municipality_Config
3. WHEN the municipality specified in Region_Setting does not have Municipality_Config data, THE App SHALL display a message indicating that bulky waste information is not yet available for the selected municipality, and SHALL NOT display empty or partial fields
4. WHEN Region_Setting changes, THE Bulky_Waste_Screen SHALL reload and display the bulky waste information for the newly selected municipality
5. IF Region_Setting is null (unset), THEN THE App SHALL not navigate to Bulky_Waste_Screen or SHALL display a message prompting the user to set their region first
6. WHILE the bulky waste information is being loaded, THE Bulky_Waste_Screen SHALL display a loading indicator

### Requirement 3: 粗大ごみ対象品目一覧

**User Story:** ユーザーとして、自分の自治体で粗大ごみとして出せる品目と手数料を一覧で確認したい。処分したい品物が粗大ごみに該当するか判断するため。

#### Acceptance Criteria

1. THE Item_List_View SHALL display all Bulky_Waste_Item entries registered for the selected municipality, sorted by item name in Japanese syllabary order (五十音順) as the default sort order
2. THE Item_List_View SHALL display the item name, category, and fee (numeric amount followed by the unit "円") for each Bulky_Waste_Item
3. WHEN a user enters a search keyword of 1 character or more, THE Item_List_View SHALL filter the displayed items to those whose item name or category contains the keyword as a partial match (substring match)
4. WHEN no items match the search keyword, THE Item_List_View SHALL display a message indicating no matching items were found
5. THE Item_List_View SHALL allow the user to switch sorting between name (Japanese syllabary order, ascending) and fee amount (ascending or descending)
6. IF the Backend_API fails to return Bulky_Waste_Item data, THEN THE Item_List_View SHALL display an error message indicating that the item list could not be loaded and provide a retry option

### Requirement 4: 品目詳細と手数料確認

**User Story:** ユーザーとして、特定の品目の詳細情報と正確な手数料を確認したい。処理券を正しい金額で購入するため。

#### Acceptance Criteria

1. WHEN a user selects a Bulky_Waste_Item from Item_List_View, THE Fee_Display SHALL display the fee detail screen for that item within 2 seconds of the user's selection
2. THE Fee_Display SHALL display the item name, size category, fee amount as an integer in yen with the currency unit label, and any additional notes stored for the item (up to 200 characters)
3. WHERE a municipality uses a size-based Fee_Structure, THE Fee_Display SHALL display the size thresholds in centimeters and the corresponding fee for each threshold tier
4. WHERE a municipality uses a weight-based Fee_Structure, THE Fee_Display SHALL display the weight ranges in kilograms and the corresponding fee for each weight tier
5. WHERE a municipality uses a fixed-per-item Fee_Structure, THE Fee_Display SHALL display the single fixed fee amount for the selected item
6. IF fee information is unavailable for a selected item, THEN THE Fee_Display SHALL display a message indicating that fee information is unavailable and display the municipality's contact phone number or web URL from Municipality_Config so the user can confirm the fee directly
7. WHEN the Fee_Display is showing a size-based or weight-based Fee_Structure, THE Fee_Display SHALL visually indicate which tier applies to the selected Bulky_Waste_Item

### Requirement 5: 申し込み手順ガイド

**User Story:** ユーザーとして、粗大ごみの申し込みから排出までの手順をステップ形式で確認したい。初めてでも迷わず手続きを完了するため。

#### Acceptance Criteria

1. THE Application_Guide SHALL display the bulky waste collection application process as a numbered step sequence with steps numbered from 1 to the total number of steps
2. THE Application_Guide SHALL include at minimum the following steps in order: item eligibility confirmation, fee confirmation, application submission, disposal ticket purchase, and item placement for collection
3. THE Application_Guide SHALL display step content specific to the Municipality_Config of the selected municipality, including municipality-specific instructions for each step
4. WHEN a step includes additional notes or tips, THE Application_Guide SHALL display the supplementary information within that step in a visually distinct area (e.g. a highlighted box or italic text)
5. IF the municipality has additional steps beyond the standard five, THEN THE Application_Guide SHALL display those additional steps in the correct order as defined in Municipality_Config

### Requirement 6: 外部申し込み窓口への遷移

**User Story:** ユーザーとして、アプリ内から自治体の公式申し込み窓口に直接アクセスしたい。別途Webサイトを探す手間を省くため。

#### Acceptance Criteria

1. WHERE a municipality supports web form Application_Method, THE External_Link_Handler SHALL display a button labeled to indicate it will open the municipality web form
2. WHERE a municipality supports phone Application_Method, THE External_Link_Handler SHALL display a button labeled to indicate it will initiate a phone call to the municipality contact number
3. WHERE a municipality supports both web form and phone Application_Method, THE External_Link_Handler SHALL display both buttons simultaneously so the user can tap one to proceed
4. WHEN a user taps the web form button, THE External_Link_Handler SHALL open the municipality web form URL using the device default browser
5. WHEN a user taps the phone button, THE External_Link_Handler SHALL display a confirmation dialog showing the municipality phone number before invoking the device phone dialer
6. IF the device cannot open the external URL, THEN THE External_Link_Handler SHALL display an error message with the URL as copyable text so the user can manually paste it into a browser
7. IF the device cannot invoke the phone dialer, THEN THE External_Link_Handler SHALL display an error message with the municipality phone number as copyable text

### Requirement 7: 申し込み状況追跡

**User Story:** ユーザーとして、粗大ごみ申し込みの進捗状況を記録・確認したい。収集日までに必要な準備を忘れないようにするため。

#### Acceptance Criteria

1. THE Status_Tracker SHALL allow users to create a local application record with the item name (maximum 50 characters), scheduled collection date (today or a future date), and current status
2. THE Status_Tracker SHALL provide status options: applied, ticket purchased, and awaiting collection, and SHALL allow the user to set or change the status in any order
3. WHEN a user updates the status of an application record, THE Status_Tracker SHALL persist the updated status locally on the device
4. WHEN the scheduled collection date is within 24 hours, THE App SHALL send a local notification reminding the user to prepare the item for collection
5. WHEN a user marks a record as completed, THE Status_Tracker SHALL change the record status to completed and move the record to an archived list that is not displayed in the active records view but remains accessible from a separate archived records section
6. IF the user attempts to create a record with an empty item name or a collection date in the past, THEN THE Status_Tracker SHALL display a validation error message indicating the invalid field and SHALL NOT create the record
7. IF the scheduled collection date has passed and the record has not been marked as completed, THEN THE Status_Tracker SHALL visually indicate that the record is overdue in the active records list

### Requirement 8: 自治体設定データの管理

**User Story:** 管理者として、各自治体の粗大ごみ情報（品目リスト、手数料、連絡先等）を管理・更新したい。情報を最新に保つため。

#### Acceptance Criteria

1. THE Backend_API SHALL provide an endpoint to retrieve Municipality_Config for a given municipality ID (5-digit code), returning within 3 seconds of the request
2. THE Backend_API SHALL provide an endpoint to retrieve the list of Bulky_Waste_Item entries for a given municipality ID, returning a maximum of 500 items per response
3. WHEN Municipality_Config data is updated on the backend, THE App SHALL reflect the updated data on next screen load without requiring an app update
4. THE Backend_API SHALL return fee information as structured data including amount (integer, 0 to 99999 yen), currency unit (yen), and applicable size or weight category name
5. IF the Backend_API does not respond within 10 seconds, THEN THE App SHALL display cached data from the last successful retrieval and display a visible indicator stating that the displayed data is from a previous retrieval and may not reflect the latest information
6. IF the municipality ID does not exist in the backend data, THEN THE Backend_API SHALL return an error response indicating that the specified municipality was not found
7. IF no cached data is available and the Backend_API is unreachable, THEN THE App SHALL display an error message indicating that municipality data could not be loaded and provide a retry option

### Requirement 9: 粗大ごみ品目の検索連携

**User Story:** ユーザーとして、既存のゴミ検索機能から粗大ごみ品目の情報にアクセスしたい。検索結果から直接詳細情報を確認するため。

#### Acceptance Criteria

1. WHEN a search result in the existing garbage search feature matches a GarbageItem that has a corresponding Bulky_Waste_Item mapping for the user's current Region_Setting municipality, THE App SHALL display a visual indicator and a tappable link to the Bulky_Waste_Screen detail within that search result tile
2. WHEN a user taps the bulky waste link in a search result, THE App SHALL navigate to the Fee_Display for the corresponding Bulky_Waste_Item within Bulky_Waste_Screen, passing the municipality from Region_Setting and the mapped Bulky_Waste_Item identifier
3. IF the corresponding Bulky_Waste_Item data is unavailable when the user taps the bulky waste link, THEN THE App SHALL display an error message indicating that bulky waste details could not be loaded and remain on the current search results screen
4. THE App SHALL use the same item name string for a GarbageItem and its corresponding Bulky_Waste_Item when they represent the same physical item, so that a character-exact comparison of the name fields yields a match
5. WHEN a GarbageItem has a Bulky_Waste_Item mapping but the user's current Region_Setting municipality does not match any available Municipality_Config, THE App SHALL not display the bulky waste link for that item
