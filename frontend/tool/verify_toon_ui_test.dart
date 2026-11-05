// Explicit widget checks against generated Toon assets, with no API/OS calls.
import 'dart:io';
import 'package:intl/date_symbol_data_local.dart';
import 'package:garbage_app/providers/calendar_provider.dart';
import 'package:garbage_app/providers/memo_provider.dart';
import 'package:garbage_app/providers/weather_provider.dart';
import 'package:garbage_app/screens/calendar_screen.dart';
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

class ReviewedToonBundle extends MunicipalityBundle {
  ReviewedToonBundle(super.files);
  @override
  Future<String> loadString(String key, {bool cache = true}) async =>
      files[key] ?? (throw StateError('Missing asset: $key'));
}

class SelectedToon extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  SelectedToon([RegionSetting? initial]) : super(AsyncValue.data(initial));
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

class NoToonOsNotifications extends NotificationService {
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
    final data = MunicipalityDataService(bundle: ReviewedToonBundle(files));
    final profile = await data.profile('38215', 'shigenobu');
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
      'Toon selection uses geographical names and preserves the selected ID',
      (tester) async {
    wide(tester);
    final data = MunicipalityDataService(bundle: ReviewedToonBundle(files));
    final selected = SelectedToon();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          prefecturesProvider
              .overrideWith((ref) async => [Prefecture(id: '38', name: '愛媛県')]),
          municipalityDataProvider.overrideWithValue(data),
          regionSettingProvider.overrideWith((ref) => selected),
          notificationServiceProvider
              .overrideWithValue(NoToonOsNotifications()),
        ],
        child: const MaterialApp(
            home: RegionSelectionScreen(updateActiveSavedRegion: false))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('東温市'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    for (final hidden in ['tn-', '未確認', '搬出時刻']) {
      expect(find.textContaining(hidden), findsNothing);
    }
    const place = '重信：山之内';
    expect(find.text(place), findsOneWidget);
    await tester.tap(find.text(place));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(selected.selected!.municipalityId, '38215');
    expect(selected.selected!.districtId, '38215-01');
    expect(selected.selected!.districtName, place);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'Toon bulky guide shows application, official link and carry-in restrictions',
      (tester) async {
    wide(tester);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ApplicationGuideView(config: bulkyConfig))));
    await tester.pumpAndSettle();
    expect(find.text('東温市の粗大ごみの出し方'), findsOneWidget);
    expect(find.text('公式の出し方を確認'), findsOneWidget);
    expect(find.textContaining('申込制の戸別収集ではなく'), findsOneWidget);
    expect(find.textContaining('大人2人'), findsOneWidget);
    expect(find.textContaining('粗大ごみを受け入れません'), findsOneWidget);
    expect(find.textContaining('A〜D'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'calendar shows local timing and an instrument notice only where relevant',
      (tester) async {
    wide(tester);
    await tester.runAsync(() => initializeDateFormatting('ja_JP'));
    final data = MunicipalityDataService(bundle: ReviewedToonBundle(files));
    final selected = SelectedToon(RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38215',
        municipalityName: '東温市',
        districtId: '38215-04',
        districtName: '重信：志津川'));
    await tester.pumpWidget(ProviderScope(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionSettingProvider.overrideWith((ref) => selected),
      focusedMonthProvider.overrideWith((ref) => DateTime(2026, 4)),
      selectedDayProvider.overrideWith((ref) => DateTime(2026, 4, 26)),
      memoForDateProvider.overrideWith((ref, date) => null),
      monthlyMemosProvider.overrideWith((ref, month) => <DateTime>{}),
      weatherForecastProvider.overrideWith((ref) async => {}),
    ], child: const MaterialApp(home: CalendarScreen())));
    await tester.pumpAndSettle();
    expect(find.textContaining('搬出時刻は地域で確認'), findsWidgets);
    expect(find.text('収集日未確認'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
