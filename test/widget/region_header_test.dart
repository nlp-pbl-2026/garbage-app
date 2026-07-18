import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:garbage_app/constants/strings.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/widgets/region_header.dart';

void main() {
  group('RegionHeader', () {
    testWidgets('地域設定済みの場合にdisplayNameが表示される', (tester) async {
      final setting = RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38201',
        municipalityName: '松山市',
        districtId: '38201-01',
        districtName: '清水地区',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            regionSettingProvider.overrideWith(
              (ref) => _FakeRegionSettingNotifier(AsyncValue.data(setting)),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              appBar: RegionHeader(),
            ),
          ),
        ),
      );

      // displayNameが表示されること
      expect(find.text('松山市 清水地区'), findsOneWidget);
      // 位置アイコンが表示されること
      expect(find.byIcon(Icons.location_on), findsOneWidget);
      // 編集アイコンが表示されること
      expect(find.byIcon(Icons.edit), findsOneWidget);
    });

    testWidgets('地域未設定の場合に未設定メッセージが表示される', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            regionSettingProvider.overrideWith(
              (ref) => _FakeRegionSettingNotifier(const AsyncValue.data(null)),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              appBar: RegionHeader(),
            ),
          ),
        ),
      );

      // 未設定メッセージが表示されること
      expect(find.text(AppStrings.regionNotSet), findsOneWidget);
      // 位置アイコンが表示されること
      expect(find.byIcon(Icons.location_on), findsOneWidget);
    });

    testWidgets('20文字超過時に省略記号付きで表示される', (tester) async {
      // 「松山市 とても長い長い長い長い地区名」→20文字を超えるので切り詰め
      final setting = RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38201',
        municipalityName: '松山市',
        districtId: '38201-99',
        districtName: 'とても長い長い長い長い地区名です',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            regionSettingProvider.overrideWith(
              (ref) => _FakeRegionSettingNotifier(AsyncValue.data(setting)),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              appBar: RegionHeader(),
            ),
          ),
        ),
      );

      // displayNameが20文字+省略記号で表示されること
      expect(find.text(setting.displayName), findsOneWidget);
      expect(setting.displayName.contains('…'), isTrue);
    });

    testWidgets('編集アイコン押下でコールバックが呼ばれる', (tester) async {
      bool callbackCalled = false;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            regionSettingProvider.overrideWith(
              (ref) => _FakeRegionSettingNotifier(const AsyncValue.data(null)),
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              appBar: RegionHeader(
                onEditPressed: () {
                  callbackCalled = true;
                },
              ),
            ),
          ),
        ),
      );

      // 編集アイコンをタップ
      await tester.tap(find.byIcon(Icons.edit));
      await tester.pump();

      expect(callbackCalled, isTrue);
    });

    testWidgets('ローディング中はCircularProgressIndicatorが表示される',
        (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            regionSettingProvider.overrideWith(
              (ref) => _FakeRegionSettingNotifier(const AsyncValue.loading()),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              appBar: RegionHeader(),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('エラー時に未設定メッセージが表示される', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            regionSettingProvider.overrideWith(
              (ref) => _FakeRegionSettingNotifier(
                AsyncValue.error(Exception('テストエラー'), StackTrace.current),
              ),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              appBar: RegionHeader(),
            ),
          ),
        ),
      );

      // エラー時も未設定メッセージが表示されること
      expect(find.text(AppStrings.regionNotSet), findsOneWidget);
    });
  });
}

/// テスト用の偽RegionSettingNotifier
class _FakeRegionSettingNotifier
    extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  _FakeRegionSettingNotifier(super.initialState);

  @override
  Future<void> loadSetting() async {}

  @override
  Future<void> saveSetting(RegionSetting setting) async {}

  @override
  RegionValidationResult validate({
    String? prefectureId,
    String? municipalityId,
    String? districtId,
  }) {
    return const RegionValidationResult.valid();
  }

  // RegionServiceへの参照は不要（テスト用）
  @override
  // ignore: override_on_non_overriding_member
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
