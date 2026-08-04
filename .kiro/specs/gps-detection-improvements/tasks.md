# Implementation Plan: GPS Detection Improvements

## Overview

GPS地区自動判定機能の包括的改善を段階的に実装する。まず抽象インターフェースとデータモデルを定義し、次にコアロジック（AddressNormalizer、GeocodingCache、GeoJsonResolver）を実装、続いてDistrictMatcherの拡張と複数エリア対応、UIの改善（複数候補表示、SnackBar改善）、最後にバックグラウンド位置監視を追加する。

## Tasks

- [x] 1. Define abstract service interfaces and data models
  - [x] 1.1 Create abstract service interfaces (AbstractLocationService, AbstractReverseGeocoder, AbstractDistrictMatcher)
    - Create `lib/services/abstract_location_service.dart` with abstract class defining checkPermission, requestPermission, isLocationServiceEnabled, getCurrentPosition
    - Create `lib/services/abstract_reverse_geocoder.dart` with abstract class defining getAddressFromCoordinates
    - Create `lib/services/abstract_district_matcher.dart` with abstract class defining loadChoumeiData, matchDistrict, matchDistrictCandidates
    - _Requirements: 7.1, 7.5, 7.6_

  - [x] 1.2 Create new data models (DistrictCandidate, GpsDetectionErrorType, AreaConfig, GeocodingCacheEntry, BackgroundMonitorState)
    - Add `DistrictCandidate` class to models (districtNumber, districtName, townName)
    - Add `GpsDetectionErrorType` enum (permissionDenied, serviceDisabled, timeout, inaccurate, geocodingFailed, outOfArea, districtNotFound, unknown)
    - Create `lib/models/area_config.dart` with AreaConfig class and AreaConfigRegistry
    - Create `lib/models/geocoding_cache_entry.dart` with GeocodingCacheEntry including Haversine distance calculation
    - Create `lib/models/background_monitor_state.dart` with sealed class hierarchy
    - _Requirements: 1.5, 9.2, 9.7, 5.1, 10.1_

  - [x] 1.3 Extend GpsDetectionState with MultipleCandidates and enhanced Error states
    - Add `GpsDetectionMultipleCandidates` state with candidates list and overflowMessage
    - Add `errorType` field (GpsDetectionErrorType) to GpsDetectionError class
    - _Requirements: 1.1, 1.6, 2.1, 2.2, 3.1, 3.2_

- [x] 2. Implement AddressNormalizer
  - [x] 2.1 Create AddressNormalizer class with normalize() and normalizeSafe() methods
    - Create `lib/services/address_normalizer.dart`
    - Implement normalization pipeline: (1) remove 「大字」 → (2) remove 「字」 → (3) remove spaces (U+3000, U+0020) → (4) convert full-width digits to half-width
    - Implement normalizeSafe() for null/empty input handling
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.7_

  - [x]* 2.2 Write property test for AddressNormalizer normalization correctness
    - **Property 1: Address normalization correctness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [x]* 2.3 Write property test for normalization safety on reference data
    - **Property 2: Normalization safety on reference data**
    - **Validates: Requirements 4.6**

  - [x]* 2.4 Write property test for raw match priority over normalized match
    - **Property 3: Raw match priority over normalized match**
    - **Validates: Requirements 4.5, 4.8**

- [x] 3. Implement GeocodingCache
  - [x] 3.1 Create GeocodingCache class with get/put/clear operations and Haversine distance logic
    - Create `lib/services/geocoding_cache.dart`
    - Implement 50m hit radius using Haversine formula
    - Implement FIFO eviction with maxEntries=100
    - Return nearest cached entry when multiple entries within 50m
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 3.2 Write property test for cache spatial hit and miss
    - **Property 7: Cache spatial hit and miss**
    - **Validates: Requirements 5.2**

  - [x]* 3.3 Write property test for cache size invariant
    - **Property 8: Cache size invariant**
    - **Validates: Requirements 5.4**

  - [x]* 3.4 Write property test for cache FIFO eviction
    - **Property 9: Cache FIFO eviction**
    - **Validates: Requirements 5.5**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement GeoJsonResolver for offline district detection
  - [x] 5.1 Create GeoJSON polygon data asset file
    - Create `assets/data/matsuyama_districts.geojson` with FeatureCollection containing district polygons
    - Each Feature has properties: district_number, district_name, and Polygon geometry
    - Update pubspec.yaml assets if needed
    - _Requirements: 6.1_

  - [x] 5.2 Implement GeoJsonResolver with ray-casting point-in-polygon algorithm
    - Create `lib/services/geojson_resolver.dart`
    - Implement loadPolygons() for async loading at app startup
    - Implement resolveDistrict(lat, lng) with ray-casting algorithm, returning DistrictMatchResult or null
    - Ensure resolveDistrict completes within 200ms
    - _Requirements: 6.2, 6.5, 6.6_

- [x] 6. Refactor existing services to implement abstract interfaces and add DI
  - [x] 6.1 Refactor GpsLocationService to implement AbstractLocationService
    - Modify `lib/services/gps_location_service.dart` to extend AbstractLocationService
    - Accept Geolocator wrapper via constructor for testability
    - _Requirements: 7.1, 7.2_

  - [x] 6.2 Refactor ReverseGeocodingService to implement AbstractReverseGeocoder
    - Modify `lib/services/reverse_geocoding_service.dart` to extend AbstractReverseGeocoder
    - _Requirements: 7.5_

  - [x] 6.3 Refactor DistrictMatcherService to implement AbstractDistrictMatcher with fuzzy matching and multi-area support
    - Modify `lib/services/district_matcher_service.dart` to extend AbstractDistrictMatcher
    - Integrate AddressNormalizer for staged matching: raw match → normalized match → prefix match
    - Add matchDistrictCandidates() returning List<DistrictCandidate> sorted by townName (Unicode ascending)
    - Accept areaId parameter and filter choumei data using AreaConfig.oldCityNameFilters
    - Cap candidate list at 50 with overflow message
    - Return error for unknown areaId
    - _Requirements: 4.5, 4.8, 7.6, 9.1, 9.3, 9.4, 9.5, 9.6, 1.1, 1.2, 1.5, 1.6_

  - [x]* 6.4 Write property tests for DistrictMatcher (Properties 4-6, 11-16)
    - **Property 4: Multiple candidate completeness**
    - **Property 5: Candidate list cap at 50**
    - **Property 6: Candidate sort order**
    - **Property 11: Town name matching correctness**
    - **Property 12: Out-of-area detection**
    - **Property 13: Unmatched town exception**
    - **Property 14: District ID format**
    - **Property 15: Area filtering correctness**
    - **Property 16: Unknown area ID error**
    - **Validates: Requirements 1.1, 1.2, 1.5, 1.6, 8.2, 8.3, 8.4, 8.5, 9.1, 9.6**

  - [x]* 6.5 Write property test for GPS accuracy validation
    - **Property 10: GPS accuracy validation**
    - **Validates: Requirements 8.1**

  - [x] 6.6 Update GpsDetectionNotifier to use abstract interfaces, GeoJsonResolver, and GeocodingCache
    - Modify `lib/providers/gps_detection_provider.dart` to depend on abstract types
    - Integrate GeoJsonResolver (try offline first, fallback to geocoding flow)
    - Integrate GeocodingCache (check cache before API call, store results after)
    - Handle MultipleCandidates state when matchDistrictCandidates returns multiple results
    - Populate GpsDetectionErrorType for each error scenario
    - Update Riverpod providers to use abstract types with overrideWithValue support
    - _Requirements: 6.2, 6.3, 6.4, 6.6, 7.3, 7.4, 5.2_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement UI improvements (SnackBars and Bottom Sheet)
  - [x] 8.1 Implement settings-open SnackBar for permission denied and service disabled errors
    - Modify `lib/screens/region_selection_screen.dart` to show SnackBar with 「設定を開く」 action button for permissionDenied/serviceDisabled errors
    - Modify `lib/screens/settings_screen.dart` with same SnackBar behavior
    - SnackBar persists until user taps action or dismisses
    - Call Geolocator.openAppSettings() on button tap
    - Do NOT auto-retry after returning from settings
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 8.2 Implement retry SnackBar for timeout and inaccuracy errors
    - Show SnackBar with 「再試行」 action button for timeout/inaccurate errors on both screens
    - SnackBar auto-dismisses after 10 seconds or on user tap
    - On retry tap: dismiss SnackBar, re-execute detectDistrict(), show loading indicator, disable GPS button
    - Allow unlimited retries on continued failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 8.3 Implement candidate selection bottom sheet for multiple matches
    - Create `lib/widgets/candidate_bottom_sheet.dart` displaying List<DistrictCandidate>
    - Show candidates sorted by townName (ascending Unicode order)
    - Each item displays districtName and townName
    - On selection: show confirmation dialog, then apply district
    - On outside tap: close bottom sheet, return to manual selection mode
    - Show overflow message when candidates exceed 50
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x]* 8.4 Write widget tests for SnackBars and bottom sheet
    - Test settings SnackBar display and action for permissionDenied/serviceDisabled
    - Test retry SnackBar display, auto-dismiss at 10s, and retry action
    - Test candidate bottom sheet display, selection, and dismiss behavior
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 1.2, 1.3, 1.4_

- [x] 9. Implement BackgroundLocationMonitor
  - [x] 9.1 Create BackgroundLocationMonitor StateNotifier
    - Create `lib/providers/background_location_monitor.dart`
    - Implement startMonitoring/stopMonitoring with 30-60 minute check intervals
    - Calculate Haversine distance between current GPS and reference coordinate
    - Trigger prompt when distance ≥ 2km AND (no prior prompt OR 24h since last prompt)
    - Implement acceptUpdate() to start GPS detection flow
    - Implement dismissPrompt() to set 24h cooldown
    - Only operate in foreground (respect "while in use" permission)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [x] 9.2 Implement background monitor UI prompt
    - Show re-detection prompt when BackgroundMonitorPrompting state is active
    - Provide "更新する" (accept) and "後で" (dismiss) options
    - On accept: start GPS detection; on failure show error with manual navigation option
    - On dismiss or implicit close (back button, backgrounded): apply 24h cooldown
    - _Requirements: 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x]* 9.3 Write property tests for BackgroundLocationMonitor (Properties 17-19)
    - **Property 17: Distance threshold detection**
    - **Property 18: Prompt trigger conditions**
    - **Property 19: Check interval bounds**
    - **Validates: Requirements 10.1, 10.2, 10.7**

- [x] 10. Implement remaining property-based tests from Requirement 8
  - [x]* 10.1 Write property tests for GPS accuracy, town name matching, out-of-area, unmatched town, and district ID format (Properties from Req 8)
    - **Property 10 (Req 8.1): GPS accuracy validation** - random accuracy values 0.0-10000.0
    - **Property 11 (Req 8.2): Town name matching correctness** - all choumei.csv town names
    - **Property 12 (Req 8.3): Out-of-area detection** - non-松山市 city names
    - **Property 13 (Req 8.4): Unmatched town exception** - generated town names not in choumei.csv
    - **Property 14 (Req 8.5): District ID format** - "{municipalityId}-{districtNumber}" pattern
    - Use glados ^1.1.1, minimum 100 iterations per property
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The project uses Flutter/Dart with Riverpod for state management
- Property-based tests use `glados: ^1.1.1` (already in dev_dependencies)
- GeoJSON polygon data for Matsuyama's 44 districts needs to be sourced or generated externally

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "3.1", "5.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "3.4", "5.2"] },
    { "id": 3, "tasks": ["6.1", "6.2", "6.3"] },
    { "id": 4, "tasks": ["2.4", "6.4", "6.5", "6.6"] },
    { "id": 5, "tasks": ["8.1", "8.2", "8.3", "9.1"] },
    { "id": 6, "tasks": ["8.4", "9.2", "9.3"] },
    { "id": 7, "tasks": ["10.1"] }
  ]
}
```
