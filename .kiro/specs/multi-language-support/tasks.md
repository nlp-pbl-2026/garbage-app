# Implementation Plan: 多言語対応 (Multi-Language Support)

## Overview

Flutter標準ローカリゼーション（flutter_localizations + gen-l10n + ARBファイル）とRiverpodによるリアクティブなロケール管理を導入し、既存AppStringsを完全移行する。バックエンドにはAccept-Language対応ミドルウェアと翻訳テーブルを追加する。フロントエンド・バックエンド共にJapanese(ja)フォールバックを統一し、5言語（ja/en/pt/zh/vi）をサポートする。

## Tasks

- [x] 1. Set up localization infrastructure
  - [x] 1.1 Configure flutter_localizations and gen-l10n
    - Add `flutter_localizations` to pubspec.yaml dependencies
    - Create `l10n.yaml` config file at `frontend/l10n.yaml` with arb-dir, template-arb-file, output-class settings
    - Create `frontend/lib/l10n/` directory
    - Create base ARB file `app_ja.arb` with all string keys migrated from `AppStrings` (including parameterized strings with ICU format and metadata annotations)
    - Run `flutter gen-l10n` to verify generation works
    - _Requirements: 6.1, 6.4, 6.6_

  - [x] 1.2 Create ARB files for all supported languages
    - Create `app_en.arb` with English translations for every key in app_ja.arb
    - Create `app_pt.arb` with Portuguese translations
    - Create `app_zh.arb` with Chinese Simplified translations
    - Create `app_vi.arb` with Vietnamese translations
    - Include garbage category names (burnable, recyclable, plastic, PET bottle, hazardous) in all files
    - _Requirements: 1.1, 1.3, 6.1, 6.3_

  - [ ]* 1.3 Write property test for ARB key completeness (Property 11)
    - **Property 11: ARB key completeness**
    - Parse all ARB files and verify every key in app_ja.arb exists in all other ARB files
    - Use `glados` to generate random subsets and verify
    - **Validates: Requirements 1.3**

  - [x] 1.4 Implement LocaleNotifier with Riverpod
    - Create `frontend/lib/providers/locale_provider.dart`
    - Implement `LocaleNotifier` extending `StateNotifier<Locale>`
    - Implement `initialize()`: read from SharedPreferences, detect system locale, validate stored code
    - Implement `setLocale(Locale)`: persist to SharedPreferences, update state (skip if same locale)
    - Implement `resolveLocale(Locale systemLocale)`: extract language prefix, match to supported list, fallback to ja
    - Define `localeProvider` as `StateNotifierProvider<LocaleNotifier, Locale>`
    - _Requirements: 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.5, 5.1, 5.2_

  - [ ]* 1.5 Write property tests for locale resolution (Properties 1, 3, 4, 10)
    - **Property 1: Frontend locale resolution correctness**
    - Test `resolveLocale()` with arbitrary locale strings: supported codes return themselves, region subtags match base language, unknown codes return 'ja'
    - **Property 3: Language preference persistence round-trip**
    - Test store and read back of each supported language code
    - **Property 4: Invalid stored preference correction**
    - Test that invalid stored values resolve to 'ja' and overwrite storage
    - **Property 10: Language selection idempotence**
    - Test that `setLocale` with same locale doesn't trigger state change or persistence write
    - **Validates: Requirements 1.2, 2.5, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.5**

- [x] 2. Wire locale into MaterialApp and migrate AppStrings
  - [x] 2.1 Update MaterialApp with localization delegates and locale binding
    - Modify `frontend/lib/app.dart` to watch `localeProvider`
    - Add `localizationsDelegates` (AppLocalizations.delegate, GlobalMaterialLocalizations, GlobalWidgetsLocalizations, GlobalCupertinoLocalizations)
    - Add `supportedLocales` list for all 5 locales
    - Set `locale` property to value from `localeProvider`
    - _Requirements: 1.1, 5.1, 5.2, 5.3, 6.4_

  - [x] 2.2 Replace all AppStrings references with AppLocalizations
    - Search for all `AppStrings.` usages across the codebase
    - Replace each reference with `AppLocalizations.of(context).keyName`
    - Remove `frontend/lib/constants/strings.dart` after all references are migrated
    - Ensure zero hard-coded user-visible strings remain in Dart source files
    - _Requirements: 6.2, 6.5_

  - [x] 2.3 Update date and number formatting to use locale
    - Update all `DateFormat` usages to pass current locale from `localeProvider`
    - Update `table_calendar` widget to use current locale for day/month labels
    - Update any `NumberFormat` usages to use locale-appropriate separators
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [ ]* 2.4 Write property test for date/number locale formatting (Property 12)
    - **Property 12: Date and number locale formatting**
    - Test that `DateFormat` produces locale-correct output for random dates × 5 locales
    - Test that `NumberFormat` uses correct grouping/decimal separators per locale
    - **Validates: Requirements 13.1, 13.4**

- [x] 3. Checkpoint - Ensure localization infrastructure works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Language Selector UI
  - [x] 4.1 Create LanguageSelector widget on settings screen
    - Create `frontend/lib/widgets/language_selector.dart`
    - Display 5 selectable options with native names: 日本語, English, Português, 中文, Tiếng Việt
    - Show visual marker (check icon) on currently selected language distinguishable without relying on color alone
    - On selection, call `localeProvider.setLocale()` — app updates immediately without navigation
    - If selected language is already active, do nothing (no reload)
    - Integrate into `frontend/lib/screens/settings_screen.dart` as a new section
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3_

  - [ ]* 4.2 Write unit tests for LanguageSelector widget
    - Test that exactly 5 options are displayed
    - Test that native names are correct
    - Test that check mark appears on active language
    - Test that selecting same language does not trigger reload
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

- [x] 5. Backend language middleware and translation tables
  - [x] 5.1 Create LanguageMiddleware for Accept-Language parsing
    - Create `backend/app/middleware/language_middleware.py`
    - Implement RFC 9110 compliant Accept-Language parsing with q-factor weighting
    - Set `request.state.language` to resolved language code
    - Handle regional variants (pt-BR→pt, zh-CN→zh, en-US→en)
    - Fall back to 'ja' for missing/malformed/unsupported header values
    - Register middleware in `backend/app/main.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 5.2 Write property test for backend Accept-Language resolution (Property 2)
    - **Property 2: Backend Accept-Language resolution correctness**
    - Use `hypothesis` to generate random Accept-Language header strings
    - Verify highest-priority supported language is returned, regional variants match base code, unsupported-only headers return 'ja'
    - **Validates: Requirements 10.1, 10.3, 10.4**

  - [x] 5.3 Create translation database tables and models
    - Create `GarbageItemTranslation` model in `backend/app/models.py` with fields: garbage_item_id, language_code, item_name, disposal_method, caution, keywords
    - Create `BulkyWasteItemTranslation` model with fields: bulky_waste_item_id, language_code, item_name, notes
    - Create `MunicipalityRomanization` model with fields: municipality_name, romanized_name
    - Add UNIQUE constraints on (item_id, language_code) pairs
    - Add CHECK constraint on language_code for supported values
    - Create database migration script to add these tables
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 10.6, 10.7, 11.3_

  - [x] 5.4 Update backend API endpoints to return localized content
    - Update garbage item query endpoints to join with translations table and return localized fields
    - Update bulky waste item endpoints to return localized item_name and notes
    - Return Japanese text as fallback when translation is missing
    - Return error detail messages in the resolved request language
    - _Requirements: 10.5, 10.6, 10.7, 10.8_

  - [ ]* 5.5 Write property test for backend localized field response (Property 13)
    - **Property 13: Backend localized field response**
    - Use `hypothesis` to generate random items with/without translations
    - Verify that when translation exists for resolved language, it is returned; otherwise Japanese text is returned
    - **Validates: Requirements 10.6, 10.7**

- [x] 6. Checkpoint - Ensure backend language support works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend GarbageItem model and search updates
  - [x] 7.1 Update GarbageItem model with localized fields
    - Add `localizedName`, `localizedDisposalMethod`, `localizedCaution`, `localizedKeywords` fields to `GarbageItem` in `frontend/lib/models/garbage_item.dart`
    - Add `displayName`, `displayDisposalMethod`, `displayCaution` getters with fallback to Japanese
    - Update `fromJson` factory to parse localized fields from API response
    - Update all UI usages to use `displayName` / `displayDisposalMethod` / `displayCaution` getters
    - _Requirements: 7.5, 7.8, 12.1, 12.2_

  - [ ]* 7.2 Write property test for garbage item translation fallback (Property 5)
    - **Property 5: Garbage item translation fallback**
    - Use `glados` to generate GarbageItem instances with some localized fields null
    - Verify display getters return Japanese text when translation is missing
    - **Validates: Requirements 7.5, 7.8, 10.8**

  - [x] 7.3 Implement dual-language search logic
    - Update search function to match against both selected language keywords/names AND Japanese keywords/names
    - Return combined unique results (no duplicates)
    - Display translated item name if translation exists, Japanese name otherwise
    - _Requirements: 7.6, 7.7, 7.8_

  - [ ]* 7.4 Write property test for dual-language search (Property 6)
    - **Property 6: Dual-language search inclusiveness**
    - Use `glados` to generate random queries and GarbageItem lists with mixed translations
    - Verify results are a superset of union of both language matches with no duplicates
    - **Validates: Requirements 7.6, 7.7**

- [x] 8. Update GeminiService for multi-language AI chat
  - [x] 8.1 Parameterize GeminiService system prompt by language
    - Update `frontend/lib/services/gemini_service.dart`
    - Add `_languageInstructions` map for all 5 supported languages
    - Build system prompt dynamically using current locale from `localeProvider`
    - Include instruction to append Japanese garbage-category terms in parentheses alongside translations
    - Update `sendMessage` to accept `languageCode` parameter
    - Display localized error messages from ARB files on API failure
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 8.2 Write property test for AI system prompt parameterization (Property 7)
    - **Property 7: AI system prompt parameterization**
    - Use `glados` to test all 5 language codes
    - Verify prompt contains language-specific instruction and the Japanese parenthetical instruction
    - **Validates: Requirements 8.3, 8.4**

- [x] 9. Update NotificationService for multi-language notifications
  - [x] 9.1 Localize notification content
    - Update `frontend/lib/services/notification_service.dart`
    - Read current language preference from SharedPreferences when composing notification text
    - Use ARB-based localized strings for notification title and body templates
    - Include translated garbage category names in notification content
    - On language change, reschedule pending notifications with new language
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 9.2 Write property test for notification text language consistency (Property 8)
    - **Property 8: Notification text language consistency**
    - Use `glados` to generate combinations of supported languages and garbage categories
    - Verify notification title/body use translations from the stored language preference
    - **Validates: Requirements 9.1, 9.2, 9.3**

- [x] 10. Municipality name display and romanization
  - [x] 10.1 Create municipality romanization data and display logic
    - Create `frontend/assets/data/municipality_romanization.json` with Japanese→romanized mappings for Ehime municipalities
    - Create utility to load and lookup romanized names
    - Update municipality display widgets to show Japanese name always, plus romanized reading when non-Japanese language is selected
    - When Japanese is selected, display municipality name without romanization
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 10.2 Write property test for municipality name invariance (Property 9)
    - **Property 9: Municipality name invariance**
    - Use `glados` to generate combinations of municipalities × languages
    - Verify Japanese name is always present, romanization appears only for non-ja locales
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**

- [x] 11. Frontend HTTP client Accept-Language header
  - [x] 11.1 Update API client to send Accept-Language header
    - Update HTTP client / API service to read current locale from `localeProvider` or SharedPreferences
    - Include `Accept-Language` header with current language code in all API requests
    - _Requirements: 10.1_

- [x] 12. Fallback handling and debug logging
  - [x] 12.1 Implement fallback logging for debug builds
    - In debug/staging builds, log a warning to console when a fallback translation is used, including the missing key name and target language code
    - In production builds, silently display fallback text without logging
    - Ensure screens never display empty or null text — always fall back to Japanese item name as minimum
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using `glados` (Dart/Flutter) and `hypothesis` (Python/Backend)
- Unit tests validate specific examples and edge cases
- The design uses Dart (Flutter) and Python (FastAPI) — no language selection needed
- ARB migration (task 2.2) is the largest single task due to the number of AppStrings references across the codebase

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["1.3", "1.5", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "4.1", "5.1", "5.3"] },
    { "id": 4, "tasks": ["2.4", "4.2", "5.2", "5.4", "11.1"] },
    { "id": 5, "tasks": ["5.5", "7.1", "8.1", "9.1", "10.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "8.2", "9.2", "10.2", "12.1"] },
    { "id": 7, "tasks": ["7.4"] }
  ]
}
```
