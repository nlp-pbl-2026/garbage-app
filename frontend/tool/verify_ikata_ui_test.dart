// Explicit widget checks against generated Ikata assets, with no API/OS calls.
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/municipality_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/settings_provider.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/widgets/bulky_waste/application_guide_view.dart';
import '../test/helpers/municipality_assets.dart' show MunicipalityBundle;

class ReviewedIkataBundle extends MunicipalityBundle {
  ReviewedIkataBundle(super.files);
  @override
  Future<String> loadString(String key, {bool cache = true}) async =>
      files[key] ?? (throw StateError('Missing asset: $key'));
}

class SelectedIkata extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  SelectedIkata() : super(const AsyncValue.data(null));
  RegionSetting? get selected => state.valueOrNull;
  @override
  Future<void> saveSetting(RegionSetting setting) async =>
      state = AsyncValue.data(setting);
  @override
  RegionValidationResult validate(
          {String? prefectureId, String? municipalityId, String? districtId}) =>
      RegionValidationResult.validate(
          prefectureId: prefectureId,
          municipalityId: municipalityId,
          districtId: districtId);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class NoIkataOsNotifications extends NotificationService {
  @override
  Future<void> updateDistrict(String districtId,
      {String municipalityId = '38201'}) async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Map<String, String> files;
  late MunicipalityConfig bulkyConfig;
  setUpAll(() async {
    files = {
      for (final f in Directory('assets/data')
          .listSync()
          .whereType<File>()
          .where((f) => f.path.endsWith('.json')))
        f.path: f.readAsStringSync()
    };
    final data = MunicipalityDataService(bundle: ReviewedIkataBundle(files));
    final profile = await data.profile('38442', 'ikata');
    bulkyConfig = MunicipalityConfig.fromJson((profile['bulky_waste']
        as Map<String, dynamic>)['config'] as Map<String, dynamic>);
  });
  // tool/ keeps this real-data test outside ordinary synthetic discovery.
  // ignore: invalid_use_of_visible_for_testing_member
  setUp(() => SharedPreferences.setMockInitialValues({}));
  void wide(WidgetTester tester) {
    tester.view.physicalSize = const Size(1200, 2200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  testWidgets(
      'Ikata selection uses geographical names and preserves the selected ID',
      (tester) async {
    wide(tester);
    final data = MunicipalityDataService(bundle: ReviewedIkataBundle(files));
    final selected = SelectedIkata();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          prefecturesProvider
              .overrideWith((ref) async => [Prefecture(id: '38', name: '愛媛県')]),
          municipalityDataProvider.overrideWithValue(data),
          regionSettingProvider.overrideWith((ref) => selected),
          notificationServiceProvider
              .overrideWithValue(NoIkataOsNotifications()),
        ],
        child: const MaterialApp(
            home: RegionSelectionScreen(updateActiveSavedRegion: false))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('伊方町'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    for (final hidden in ['A-1', 'B-3', 'C-2', '曜', '未確認']) {
      expect(find.textContaining(hidden), findsNothing);
    }
    const place = '伊方地域：河内、湊浦、小中浦、中浦、川永田、豊之浦';
    expect(find.text(place), findsOneWidget);
    await tester.tap(find.text(place));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(selected.selected!.municipalityId, '38442');
    expect(selected.selected!.districtId, '38442-01');
    expect(selected.selected!.districtName, place);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'Ikata bulky guide shows application, official link and carry-in restrictions',
      (tester) async {
    wide(tester);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ApplicationGuideView(config: bulkyConfig))));
    await tester.pumpAndSettle();
    expect(find.text('伊方町の粗大ごみ申し込み手順'), findsOneWidget);
    expect(find.text('公式の出し方を確認'), findsOneWidget);
    expect(find.textContaining('このアプリからは申し込めません'), findsOneWidget);
    expect(find.textContaining('可燃ごみ・禁止品は搬入できません'), findsOneWidget);
    expect(find.textContaining('A〜D'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
