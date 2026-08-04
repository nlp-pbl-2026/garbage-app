import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/gps_detection_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';

import 'helpers/mock_services.dart';
import 'settings_snackbar_test.dart' show FakeRegionSettingNotifier;

/// 再試行SnackBarのウィジェットテスト
///
/// Validates: Requirements 3.1, 3.2
/// - timeout エラー時に「再試行」ボタン付きSnackBarが表示される
/// - inaccurate エラー時に「再試行」ボタン付きSnackBarが表示される
/// - SnackBarは10秒後に自動非表示される
/// - 「再試行」タップでGPS判定が再実行される
void main() {
  group('Retry SnackBar - RegionSelectionScreen', () {
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
      'timeout エラー時にSnackBarが「再試行」ボタンとともに表示される',
      (tester) async {
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior =
            () => throw LocationTimeoutException();

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
          find.text(LocationTimeoutException().userMessage),
          findsOneWidget,
        );
        // 「再試行」ボタンが表示される
        expect(find.text('再試行'), findsOneWidget);
      },
    );

    testWidgets(
      'inaccurate エラー時にSnackBarが「再試行」ボタンとともに表示される',
      (tester) async {
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior =
            () => throw LocationInaccurateException();

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
          find.text(LocationInaccurateException().userMessage),
          findsOneWidget,
        );
        // 「再試行」ボタンが表示される
        expect(find.text('再試行'), findsOneWidget);
      },
    );

    testWidgets(
      'Retry SnackBarは10秒後に自動非表示される',
      (tester) async {
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior =
            () => throw LocationTimeoutException();

        await tester.pumpWidget(buildTestWidget(mockLocationService));
        await tester.pumpAndSettle();

        // GPS判定ボタンをタップ
        await tester.tap(find.text('現在地から設定'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // SnackBarが表示される
        expect(find.byType(SnackBar), findsOneWidget);

        // 5秒後にまだ表示されている
        await tester.pump(const Duration(seconds: 5));
        expect(find.byType(SnackBar), findsOneWidget);

        // SnackBarのduration=10秒であることを検証（SnackBarウィジェットのdurationプロパティ確認）
        final snackBar = tester.widget<SnackBar>(find.byType(SnackBar));
        expect(snackBar.duration, const Duration(seconds: 10));
      },
    );

    testWidgets(
      '「再試行」タップでGPS判定が再実行される',
      (tester) async {
        int callCount = 0;
        final mockLocationService = MockLocationService();
        mockLocationService.getCurrentPositionBehavior = () {
          callCount++;
          throw LocationTimeoutException();
        };

        await tester.pumpWidget(buildTestWidget(mockLocationService));
        await tester.pumpAndSettle();

        // GPS判定ボタンをタップ（1回目）
        await tester.tap(find.text('現在地から設定'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(callCount, 1);

        // 「再試行」ボタンをタップ（2回目のGPS判定が実行される）
        await tester.tap(find.text('再試行'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        expect(callCount, 2);
      },
    );
  });
}
