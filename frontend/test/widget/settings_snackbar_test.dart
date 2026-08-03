import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/gps_detection_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';

import 'helpers/mock_services.dart';

/// 設定誘導SnackBarのウィジェットテスト
///
/// Validates: Requirements 2.1, 2.2
/// - permissionDenied エラー時に「設定を開く」ボタン付きSnackBarが表示される
/// - serviceDisabled エラー時に「設定を開く」ボタン付きSnackBarが表示される
/// - SnackBarはユーザー操作まで維持される（自動非表示しない）
void main() {
  group('Settings SnackBar - RegionSelectionScreen', () {
    Widget buildTestWidget(MockLocationService mockLocationService) {
      return ProviderScope(
        overrides: [
          gpsLocationServiceProvider.overrideWithValue(mockLocationService),
          districtMatcherServiceProvider
              .overrideWithValue(MockDistrictMatcher()),
          reverseGeocodingServiceProvider
              .overrideWithValue(MockReverseGeocoder()),
          geoJsonResolverProvider.overrideWithValue(MockGeoJsonResolver()),
          geocodingCacheProvider.overrideWithValue(MockGeocodingCache()),
          prefecturesProvider.overrideWith((ref) async => <Prefecture>[]),
          regionSettingProvider.overrideWith(
            (ref) => FakeRegionSettingNotifier(),
          ),
        ],
        child: const MaterialApp(
          home: RegionSelectionScreen(),
        ),
      );
    }

    testWidgets(
      'permissionDenied 時にSnackBarが「設定を開く」ボタンとともに表示される',
      (tester) async {
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior =
            () => throw LocationPermissionDeniedException();

        await tester.pumpWidget(buildTestWidget(mockLocationService));
        await tester.pumpAndSettle();

        // GPS判定ボタンをタップ
        await tester.tap(find.text('現在地から設定'));
        // detectDistrict()のasync処理を完了させる
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // SnackBarが表示される
        expect(find.byType(SnackBar), findsOneWidget);
        // エラーメッセージが表示される
        expect(
          find.text(LocationPermissionDeniedException().userMessage),
          findsOneWidget,
        );
        // 「設定を開く」ボタンが表示される
        expect(find.text('設定を開く'), findsOneWidget);
      },
    );

    testWidgets(
      'serviceDisabled 時にSnackBarが「設定を開く」ボタンとともに表示される',
      (tester) async {
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior =
            () => throw LocationServiceDisabledException();

        await tester.pumpWidget(buildTestWidget(mockLocationService));
        await tester.pumpAndSettle();

        // GPS判定ボタンをタップ
        await tester.tap(find.text('現在地から設定'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // SnackBarが表示される
        expect(find.byType(SnackBar), findsOneWidget);
        // エラーメッセージが表示される
        expect(
          find.text(LocationServiceDisabledException().userMessage),
          findsOneWidget,
        );
        // 「設定を開く」ボタンが表示される
        expect(find.text('設定を開く'), findsOneWidget);
      },
    );

    testWidgets(
      'Settings SnackBarは自動非表示しない（長時間表示を維持する）',
      (tester) async {
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior =
            () => throw LocationPermissionDeniedException();

        await tester.pumpWidget(buildTestWidget(mockLocationService));
        await tester.pumpAndSettle();

        // GPS判定ボタンをタップ
        await tester.tap(find.text('現在地から設定'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // SnackBarが表示される
        expect(find.byType(SnackBar), findsOneWidget);

        // 30秒経過してもSnackBarが維持される（自動非表示しない）
        await tester.pump(const Duration(seconds: 30));
        expect(find.byType(SnackBar), findsOneWidget);
        expect(find.text('設定を開く'), findsOneWidget);
      },
    );
  });
}

/// テスト用の偽RegionSettingNotifier
class FakeRegionSettingNotifier
    extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  FakeRegionSettingNotifier() : super(const AsyncValue.data(null));

  @override
  Future<void> loadSetting() async {}

  @override
  Future<void> saveSetting(RegionSetting setting) async {
    state = AsyncValue.data(setting);
  }

  @override
  RegionValidationResult validate({
    String? prefectureId,
    String? municipalityId,
    String? districtId,
  }) {
    return const RegionValidationResult.valid();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
