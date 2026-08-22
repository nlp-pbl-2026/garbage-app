# Requirements Document

## Introduction

愛媛県向けゴミ出しアプリケーションの多言語対応（国際化）機能。愛媛県在住の外国人住民が母国語でアプリを利用できるようにするため、日本語（デフォルト）、英語、ポルトガル語、中国語（簡体字）、ベトナム語の5言語をサポートする。Flutterの標準ローカリゼーションフレームワーク（flutter_localizations）およびARBファイルを使用し、既存のAppStringsハードコード文字列から移行する。バックエンドAPIもAccept-Languageヘッダーによる多言語対応を行う。対象言語はすべて左から右（LTR）方向のため、RTLレイアウト対応は不要とする。

## Glossary

- **App**: 愛媛県向けゴミ出しアプリケーション（Flutter製フロントエンド + FastAPIバックエンド）
- **Localization_Service**: アプリ内の翻訳テキスト解決およびロケール管理を担当するサービス（flutter_localizationsおよびARBファイルベース）
- **Language_Selector**: 設定画面内で表示言語を切り替えるUIコンポーネント
- **ARB_Files**: Application Resource Bundle形式の翻訳ファイル（各言語ごとに1ファイル: app_ja.arb, app_en.arb, app_pt.arb, app_zh.arb, app_vi.arb）
- **Garbage_Item_Database**: ゴミ品目名、出し方、注意事項を含むデータベース（SQLite）
- **AI_Chat_Service**: ユーザーの質問に回答するAIチャット機能（Gemini API利用）
- **Notification_Service**: 収集リマインダー等のプッシュ通知を送信するサービス
- **Backend_API**: FastAPIで実装されたバックエンドREST API
- **Supported_Languages**: 日本語(ja)、英語(en)、ポルトガル語(pt)、中国語簡体字(zh)、ベトナム語(vi)の5言語
- **System_Locale**: ユーザーの端末OSに設定されている言語設定
- **Preference_Storage**: ユーザーの言語設定をローカルに永続化するストレージ（SharedPreferences）
- **Accept_Language_Header**: HTTPリクエストヘッダーで、クライアントが希望する応答言語を示す標準ヘッダー

## Requirements

### Requirement 1: 対応言語の定義

**User Story:** As a foreign resident of Ehime prefecture, I want to use the app in my native language, so that I can understand garbage disposal rules without Japanese proficiency.

#### Acceptance Criteria

1. THE App SHALL register the following locale identifiers as Supported_Languages: Japanese (ja), English (en), Portuguese (pt), Chinese Simplified (zh), and Vietnamese (vi)
2. IF no stored user language preference exists and the System_Locale does not match any of the Supported_Languages, THEN THE App SHALL set the active language to Japanese (ja)
3. THE Localization_Service SHALL provide translations for every UI string key defined in the base Japanese ARB file (app_ja.arb) in each of the remaining Supported_Languages, such that no ARB file for a Supported_Language has fewer keys than app_ja.arb
4. WHEN the App is set to any of the Supported_Languages, THE App SHALL render all navigation labels, screen titles, button labels, input placeholders, error messages, and confirmation dialogs in that language

### Requirement 2: 言語選択UI

**User Story:** As an app user, I want to switch the display language from the settings screen, so that I can choose the language I understand best.

#### Acceptance Criteria

1. THE Language_Selector SHALL display exactly 5 selectable options corresponding to the Supported_Languages (ja, en, pt, zh, vi) on the settings screen
2. THE Language_Selector SHALL display each language option using the native name of that language: "日本語", "English", "Português", "中文", "Tiếng Việt"
3. THE Language_Selector SHALL indicate the currently selected language with a visual marker that is distinguishable from unselected options without relying solely on color
4. WHEN the user selects a language, THE App SHALL apply the selected language to all visible UI text, navigation labels, and screen titles within 1 second without requiring navigation away from the settings screen
5. WHEN the user selects a language that is already the currently active language, THE Language_Selector SHALL maintain the current state without triggering a language reload

### Requirement 3: システムロケールによる初期言語設定

**User Story:** As a new user, I want the app to detect my device language and display content in that language automatically, so that I can start using the app without manual configuration.

#### Acceptance Criteria

1. WHEN the App launches for the first time with no stored language preference, THE Localization_Service SHALL detect the System_Locale before rendering the first screen
2. WHEN the System_Locale exactly matches one of the Supported_Languages language codes (ja, en, pt, zh, vi), THE Localization_Service SHALL set the app language to that matching language
3. WHEN the System_Locale does not match any of the Supported_Languages either by exact match or language code prefix, THE Localization_Service SHALL set the app language to Japanese (ja)
4. WHEN the System_Locale contains a region subtag and the language code portion matches a Supported_Language (e.g., "pt-BR" matching "pt", "zh-TW" matching "zh", "en-US" matching "en"), THE Localization_Service SHALL set the app language to the matching Supported_Language
5. IF the System_Locale cannot be detected due to a platform error, THEN THE Localization_Service SHALL set the app language to Japanese (ja)

### Requirement 4: 言語設定の永続化

**User Story:** As a user, I want my language choice to be remembered across app restarts, so that I do not have to re-select my language every time I open the app.

#### Acceptance Criteria

1. WHEN the user selects a language, THE Preference_Storage SHALL persist the selected language code (one of: ja, en, pt, zh, vi) locally on the device within 500 milliseconds of the selection
2. WHEN the App launches with a stored language preference, THE Localization_Service SHALL apply the stored language preference before rendering the first user-visible screen
3. THE Preference_Storage SHALL store the language preference independently of the user authentication state such that uninstalling and reinstalling the app is the only action that clears the preference
4. WHEN the user logs out and logs back in, THE Preference_Storage SHALL retain the previously stored language preference
5. IF the stored language preference contains an invalid or unrecognized language code, THEN THE Localization_Service SHALL fall back to Japanese (ja) and overwrite the invalid stored value with "ja"

### Requirement 5: 即座の言語切替

**User Story:** As a user, I want the language to change immediately when I select a new one, so that I can see the effect of my choice without restarting the app.

#### Acceptance Criteria

1. WHEN the user changes the language setting, THE App SHALL update all visible UI text to the newly selected language within 1 second of the selection
2. WHEN the user changes the language setting, THE App SHALL update the language without requiring an app restart or manual page navigation
3. WHEN the user changes the language setting, THE App SHALL re-render all currently displayed screens with the updated translations while preserving navigation state and user input

### Requirement 6: UI文字列のARBファイル管理

**User Story:** As a developer, I want all UI strings managed via ARB-based localization files, so that translations are maintainable and follow Flutter's standard localization framework.

#### Acceptance Criteria

1. THE Localization_Service SHALL use ARB_Files as the sole source for all UI string translations, with one ARB file per Supported_Language (app_ja.arb, app_en.arb, app_pt.arb, app_zh.arb, app_vi.arb)
2. THE ARB_Files SHALL contain translations for all navigation tab labels, screen titles, button labels, error messages, confirmation dialogs, and feedback messages, with zero hard-coded user-visible strings remaining in Dart source files
3. THE ARB_Files SHALL contain translations for all garbage category names (burnable, recyclable, plastic, PET bottle, hazardous) in each of the 5 Supported_Languages
4. THE App SHALL use flutter_localizations package for locale resolution and delegate registration
5. THE App SHALL contain zero references to the AppStrings constants class, with all former AppStrings usages replaced by ARB-based localized string lookups
6. THE ARB_Files SHALL use the ICU message format for parameterized strings (e.g., date placeholders, item counts) and each parameterized string SHALL include metadata annotations describing the parameters

### Requirement 7: ゴミ品目データの多言語対応

**User Story:** As a foreign resident, I want garbage item names and disposal instructions to be shown in my language, so that I can correctly sort and dispose of my waste.

#### Acceptance Criteria

1. THE Garbage_Item_Database SHALL store translated item names for each of the Supported_Languages where translations are available
2. THE Garbage_Item_Database SHALL store translated disposal methods for each of the Supported_Languages where translations are available
3. THE Garbage_Item_Database SHALL store translated caution notes for each of the Supported_Languages where translations are available
4. THE Garbage_Item_Database SHALL store translated search keywords for each of the Supported_Languages where translations are available
5. WHEN a translation is not available for a garbage item's name, disposalMethod, or caution field, THE App SHALL display the Japanese text for that field as a fallback
6. THE App SHALL allow users to search for garbage items using search terms in the selected language, matching against translated item names and translated keywords for that language
7. WHEN the user searches in a non-Japanese language, THE App SHALL also search against the Japanese item names and Japanese keywords, and return the combined unique results from both language matches
8. WHEN displaying search results for a non-Japanese language, THE App SHALL show the translated item name if a translation exists, or the Japanese item name if no translation is available

### Requirement 8: AIチャットの多言語対応

**User Story:** As a foreign resident, I want to ask questions about garbage disposal in my preferred language and receive answers in that language, so that I can communicate naturally with the AI assistant.

#### Acceptance Criteria

1. WHEN the user sends a message to the AI_Chat_Service, THE AI_Chat_Service SHALL generate a response in the user's selected language from the supported set (Japanese, English, Chinese, Vietnamese, Portuguese)
2. THE AI_Chat_Service SHALL process user input written in the user's selected language without rejecting or misinterpreting the input due to language encoding or character set
3. THE AI_Chat_Service SHALL include a system prompt parameterized by the user's selected language that instructs the AI model to respond exclusively in that language
4. WHEN the AI_Chat_Service response includes garbage-category terminology (e.g., 可燃ごみ, 資源ごみ, プラスチック製容器包装, 粗大ごみ), THE AI_Chat_Service SHALL include the original Japanese term in parentheses alongside the translated term
5. IF the AI_Chat_Service receives an API error or fails to generate a response, THEN THE AI_Chat_Service SHALL display an error message in the user's selected language indicating that the request could not be completed

### Requirement 9: 通知の多言語対応

**User Story:** As a foreign resident, I want to receive collection reminders in my preferred language, so that I can understand the notification content without translation assistance.

#### Acceptance Criteria

1. WHEN the Notification_Service sends a collection reminder, THE Notification_Service SHALL compose both the notification title and body text in the user's currently stored language preference
2. WHEN the Notification_Service sends an error or informational notification, THE Notification_Service SHALL compose the notification text in the user's currently stored language preference
3. THE Notification_Service SHALL include garbage category names translated into the user's selected language within notification content
4. WHEN the user changes the language preference, THE Notification_Service SHALL use the updated language for all subsequently scheduled notifications

### Requirement 10: バックエンドAPIの多言語対応

**User Story:** As a developer, I want the backend API to return localized content based on the client's preferred language, so that the frontend can display consistent localized messages.

#### Acceptance Criteria

1. WHEN the Backend_API receives a request with an Accept_Language_Header containing one or more language tags, THE Backend_API SHALL select the highest-priority language tag that matches a Supported_Language, using the quality-value (q-factor) weighting defined in RFC 9110, and use that language for response content
2. WHEN the Backend_API receives a request without an Accept_Language_Header, THE Backend_API SHALL use Japanese (ja) as the default response language
3. WHEN the Accept_Language_Header specifies only languages not in Supported_Languages, THE Backend_API SHALL fall back to Japanese (ja)
4. WHEN the Accept_Language_Header contains a regional variant (e.g., "en-US", "pt-BR", "zh-CN"), THE Backend_API SHALL match it to the corresponding base Supported_Language code (en, pt, zh)
5. WHEN the Backend_API returns an error response, THE Backend_API SHALL return the error detail message in the resolved request language
6. WHEN the Backend_API returns garbage item data, THE Backend_API SHALL return the item_name and disposal_method fields in the resolved request language
7. WHEN the Backend_API returns bulky waste item data, THE Backend_API SHALL return the item_name and notes fields in the resolved request language
8. IF a translation is not available for a specific item field in the resolved request language, THEN THE Backend_API SHALL return the Japanese (ja) text for that field as a fallback

### Requirement 11: 固有名詞の取り扱い

**User Story:** As a user, I want municipality names and official terms to remain in their original Japanese form, so that I can correctly identify locations and forms when interacting with local government.

#### Acceptance Criteria

1. THE App SHALL display municipality names (市区町村名) in their original Japanese characters regardless of the selected language
2. THE App SHALL display district names (地区名) in their original Japanese characters regardless of the selected language
3. WHERE a non-Japanese language is selected, THE App SHALL display a romanized reading in Latin alphabet characters (e.g., "Matsuyama-shi", "Imabari-shi") adjacent to the Japanese municipality name
4. WHERE Japanese is selected as the language, THE App SHALL display municipality names without romanized reading

### Requirement 12: フォールバック処理

**User Story:** As a developer, I want the app to gracefully handle missing translations, so that users always see meaningful content even if a translation is incomplete.

#### Acceptance Criteria

1. IF a translated string is missing for the selected language in the ARB_Files, THEN THE Localization_Service SHALL fall back to the Japanese (ja) translation and display the Japanese text in place of the missing translation
2. IF both the selected language and Japanese translations are missing for a garbage item field, THEN THE App SHALL display the Japanese item name (品目名) as a minimum identifier so the screen is never left with an empty or null text display
3. WHILE the App is running in a non-production environment (debug or staging build), THE Localization_Service SHALL log a warning message to the debug console each time a fallback translation is used, including the missing key name and the target language code
4. IF a fallback translation is used in a production environment, THEN THE Localization_Service SHALL silently display the fallback text without logging or user-visible error indicators

### Requirement 13: 日付・数値のロケール対応

**User Story:** As a user, I want dates and numbers displayed in a format appropriate for my language, so that I can read them naturally.

#### Acceptance Criteria

1. THE App SHALL format all dates according to the conventions of the selected language locale using the intl package's DateFormat class (e.g., "2024年1月15日" for ja, "January 15, 2024" for en, "15/01/2024" for pt)
2. THE App SHALL format calendar day-of-week labels and month names in the table_calendar widget according to the selected language locale
3. WHEN the selected language changes, THE App SHALL update all currently displayed date and number formats to match the new language conventions without requiring screen navigation or app restart
4. THE App SHALL format numeric values using the selected language locale's grouping and decimal separators (e.g., "1,000" for en/ja, "1.000" for pt)
