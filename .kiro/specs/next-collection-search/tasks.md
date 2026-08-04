# Implementation Plan: Next Collection Search

## Overview

カレンダー画面に「カテゴリ別次回収集日検索パネル（Collection Search Panel）」を追加する。既存の `ScheduleService.getNextCollectionDate()` を活用し、Riverpod FutureProvider.family パターンで5カテゴリの次回収集日を一覧表示する。カードタップでカレンダー連動を実現する。

## Tasks

- [ ] 1. ユーティリティとプロバイダーの実装
  - [ ] 1.1 Create `RemainingDaysFormatter` utility class
    - Create `lib/utils/remaining_days_formatter.dart`
    - Implement `format(DateTime nextDate, DateTime today)` returning "今日" / "明日" / "あとN日"
    - Implement `formatCollectionDate(DateTime date)` returning "M月d日（曜日）" format using Japanese weekday characters (月/火/水/木/金/土/日)
    - Both methods are pure static functions for testability
    - _Requirements: 1.4, 3.1, 3.2, 3.3_

  - [ ]* 1.2 Write property tests for `RemainingDaysFormatter`
    - **Property 1: Collection date formatting produces valid pattern**
    - **Property 2: Remaining days formatter correctness**
    - Use `fast_check` package for property-based testing
    - Create `test/utils/remaining_days_formatter_test.dart`
    - Minimum 100 iterations per property
    - **Validates: Requirements 1.4, 3.1, 3.2, 3.3**

  - [ ] 1.3 Add `nextCollectionDateProvider` to calendar providers
    - Add `FutureProvider.family<DateTime?, GarbageCategory>` to `lib/providers/calendar_provider.dart`
    - Watch `regionSettingProvider` for district ID
    - Use `scheduleServiceProvider` to call `getNextCollectionDate(districtId, category.toJsonString())`
    - Return null when region setting is not configured
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 1.4 Write unit tests for `nextCollectionDateProvider`
    - Test that provider returns null when regionSetting is null
    - Test that provider calls ScheduleService with correct parameters
    - Test that provider re-calculates when region setting changes
    - Create `test/providers/next_collection_date_provider_test.dart`
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 2. Checkpoint - ユーティリティとプロバイダーの検証
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. CategoryCard ウィジェットの実装
  - [ ] 3.1 Create `CategoryCard` widget
    - Create `lib/widgets/category_card.dart`
    - Accept `GarbageCategory category` as required parameter
    - Watch `nextCollectionDateProvider(category)` for async date data
    - Display category color bar (using `CategoryColors.getColor()`), category name (using `CategoryColors.getLabel()`), formatted date, and remaining days
    - Show `CircularProgressIndicator` during loading state
    - Show "予定なし" when date is null or on error
    - On tap: update `selectedDayProvider` to the collection date; if date's month differs from `focusedMonthProvider`, update `focusedMonthProvider` accordingly
    - Disable tap when date is null
    - _Requirements: 1.2, 1.4, 3.1, 3.2, 3.3, 4.1, 4.3, 5.1, 5.2_

  - [ ]* 3.2 Write widget tests for `CategoryCard`
    - Test category name, color, and date display
    - Test loading indicator display
    - Test "予定なし" display when date is null
    - Test tap updates `selectedDayProvider`
    - Test tap updates `focusedMonthProvider` when month differs
    - Create `test/widgets/category_card_test.dart`
    - _Requirements: 1.2, 3.1, 3.2, 3.3, 4.1, 4.3, 5.1, 5.2_

- [ ] 4. CollectionSearchPanel ウィジェットの実装
  - [ ] 4.1 Create `CollectionSearchPanel` widget
    - Create `lib/widgets/collection_search_panel.dart`
    - Display all 5 `CategoryCard` widgets in fixed order: burnable, recyclable, plastic, petBottle, hazardous
    - Watch `regionSettingProvider` to check if district is configured
    - Show "地域を設定してください" message when region is not set
    - Use horizontal scrollable layout or vertical list for category cards
    - _Requirements: 1.1, 1.3, 4.2_

  - [ ]* 4.2 Write widget tests for `CollectionSearchPanel`
    - Test all 5 category cards are rendered
    - Test correct category display order
    - Test "地域を設定してください" message when region is not set
    - Create `test/widgets/collection_search_panel_test.dart`
    - _Requirements: 1.1, 1.3, 4.2_

- [ ] 5. カレンダー画面への統合
  - [ ] 5.1 Integrate `CollectionSearchPanel` into `CalendarScreen`
    - Modify `lib/screens/calendar_screen.dart`
    - Add `CollectionSearchPanel` between the next collection banner (`_buildNextCollectionBanner`) and the calendar body (`Expanded` section)
    - Import `collection_search_panel.dart`
    - Ensure the panel does not break the existing layout or scroll behavior
    - _Requirements: 1.1, 5.1, 5.2_

- [ ] 6. Final checkpoint - 全テスト実行と最終確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit/widget tests validate specific examples and edge cases
- No backend changes needed — all data comes from existing `ScheduleService.getNextCollectionDate()`
- The `fast_check` package is used for property-based testing (not glados)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1"] },
    { "id": 4, "tasks": ["4.2", "5.1"] }
  ]
}
```
