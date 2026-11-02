// Explicit UI checks using the generated official assets, without API/OS calls.
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:garbage_app/models/collection_status.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/models/waste_guide_result.dart';
import 'package:garbage_app/providers/calendar_provider.dart';
import 'package:garbage_app/providers/memo_provider.dart';
import 'package:garbage_app/providers/municipality_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/settings_provider.dart';
import 'package:garbage_app/providers/weather_provider.dart';
import 'package:garbage_app/screens/calendar_screen.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';
import 'package:garbage_app/screens/search_screen.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/waste_guide_service.dart';
import '../test/helpers/municipality_assets.dart' show MunicipalityBundle;

// Read the actual generated JSON, but avoid CachingAssetBundle's background
// isolate for large calendars inside a widget test's fake async zone.
class ReviewedBundle extends MunicipalityBundle {
  ReviewedBundle(super.files);
  @override
  Future<String> loadString(String key, {bool cache = true}) async =>
      files[key] ?? (throw StateError('Missing reviewed asset: $key'));
}

class SelectedIyo extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  SelectedIyo()
      : super(AsyncValue.data(RegionSetting(
          prefectureId: '38',
          prefectureName: '愛媛県',
          municipalityId: '38210',
          municipalityName: '伊予市',
          districtId: '38210-iyo-hiraoka',
          districtName: '平岡、鵜崎',
        )));
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

class NoOsNotifications extends NotificationService {
  @override
  Future<void> updateDistrict(String districtId,
      {String municipalityId = '38201'}) async {}
}

class FixedGuide extends WasteGuideService {
  final WasteGuideResult result;
  FixedGuide(this.result);
  @override
  Future<WasteGuideResult> classify(
          {required String query,
          required RegionSetting region,
          SearchImageInput? image,
          List<Map<String, String>> clarifications = const [],
          void Function(SearchPipelineStage)? onStageChanged}) async =>
      result;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Map<String, String> assetFiles;
  late Map<String, CollectionStatus> sharedStatuses;
  setUpAll(() async {
    await initializeDateFormatting('ja_JP');
    assetFiles = {
      for (final file in Directory('assets/data')
          .listSync()
          .whereType<File>()
          .where((f) => f.path.endsWith('.json')))
        file.path: file.readAsStringSync()
    };
    sharedStatuses = await ScheduleService(
            data: MunicipalityDataService(bundle: ReviewedBundle(assetFiles)),
            municipalityId: '38210')
        .collectionStatuses('38210-iyo-hiraoka');
  });
  // Explicit test in tool/ so ordinary flutter test needs no official assets.
  // ignore: invalid_use_of_visible_for_testing_member
  setUp(() => SharedPreferences.setMockInitialValues({}));
  void wideScreen(WidgetTester tester) {
    tester.view.physicalSize = const Size(1000, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  testWidgets(
      'Iyo selection contains place names and no collection warning or rules',
      (tester) async {
    wideScreen(tester);
    final selected = SelectedIyo();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          prefecturesProvider
              .overrideWith((ref) async => [Prefecture(id: '38', name: '愛媛県')]),
          municipalityDataProvider.overrideWithValue(
              MunicipalityDataService(bundle: ReviewedBundle(assetFiles))),
          regionSettingProvider.overrideWith((ref) => selected),
          notificationServiceProvider.overrideWithValue(NoOsNotifications()),
        ],
        child: const MaterialApp(
            home: RegionSelectionScreen(updateActiveSavedRegion: false))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('伊予市'));
    await tester.pumpAndSettle();
    expect(find.textContaining('未確認'), findsNothing);
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    expect(find.text('平岡、鵜崎'), findsOneWidget);
    for (final internal in ['未確認', '紙類', '火曜', '金曜', 'iy-iyo', '毎月第']) {
      expect(find.textContaining(internal), findsNothing);
    }
    await tester.tap(find.text('平岡、鵜崎'));
    await tester.pumpAndSettle();
    expect(find.textContaining('未確認'), findsNothing);
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(selected.selected!.districtId, '38210-iyo-hiraoka');
    expect(selected.selected!.districtName, '平岡、鵜崎');
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'calendar details show the warning only when an unverified stream is opened',
      (tester) async {
    wideScreen(tester);
    final data = MunicipalityDataService(bundle: ReviewedBundle(assetFiles));
    final states = sharedStatuses;
    final message = states['paper']!.message!;
    await tester.pumpWidget(ProviderScope(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionSettingProvider.overrideWith((ref) => SelectedIyo()),
      scheduleServiceProvider.overrideWithValue(ScheduleService(
          data: data,
          municipalityId: '38210',
          clock: () => DateTime(2026, 11, 1))),
      focusedMonthProvider.overrideWith((ref) => DateTime(2026, 11)),
      selectedDayProvider.overrideWith((ref) => DateTime(2026, 11, 1)),
      memoForDateProvider.overrideWith((ref, date) => null),
      monthlyMemosProvider.overrideWith((ref, month) => <DateTime>{}),
      weatherForecastProvider.overrideWith((ref) async => {}),
    ], child: const MaterialApp(home: CalendarScreen())));
    await tester.pumpAndSettle();
    expect(find.text('収集日未確認'), findsNWidgets(5));
    expect(find.text(message), findsNothing);
    await tester.ensureVisible(find.text('燃えるごみ').last);
    await tester.tap(find.text('燃えるごみ').last);
    await tester.pumpAndSettle();
    expect(find.text(message), findsNothing);
    expect(find.text('公式カレンダーを確認'), findsNothing);
    Navigator.of(tester.element(find.text('燃えるごみの収集日'))).pop();
    await tester.pumpAndSettle();
    for (final label in ['びん類', 'ペットボトル', '燃えないその他ごみ', '有害ごみ', '紙類']) {
      await tester.ensureVisible(find.text(label).last);
      await tester.tap(find.text(label).last);
      await tester.pumpAndSettle();
      expect(find.text(message), findsOneWidget);
      expect(find.text('公式カレンダーを確認'), findsOneWidget);
      Navigator.of(tester.element(find.text('公式カレンダーを確認'))).pop();
      await tester.pumpAndSettle();
    }
    expect(tester.takeException(), isNull);
  });

  for (final unverified in [true, false]) {
    testWidgets(
        'search ${unverified ? 'shows' : 'omits'} unverified notice according to API status',
        (tester) async {
      wideScreen(tester);
      final states = sharedStatuses;
      final state = states['paper']!;
      final result = WasteGuideResult(
          status: 'answered',
          rewrittenQuery: unverified ? '新聞紙' : '生ごみ',
          answer: unverified ? '新聞紙は紙類です。収集日は未確認です。' : '生ごみは燃えるごみです。',
          collectionStatus:
              unverified ? state : const CollectionStatus('scheduled'),
          nextCollection: NextCollection(
              date: '2026-11-02',
              displayDate: unverified ? '推測した日付' : '確認済みの収集日',
              collectionType: unverified ? '紙類' : '燃えるごみ'),
          sources: const []);
      await tester.pumpWidget(ProviderScope(overrides: [
        regionSettingProvider.overrideWith((ref) => SelectedIyo()),
      ], child: MaterialApp(home: SearchScreen(service: FixedGuide(result)))));
      await tester.enterText(find.byType(TextField).first, '確認する品物');
      await tester.tap(find.text('調べる'));
      await tester.pump();
      FocusManager.instance.primaryFocus?.unfocus();
      // SearchPipelineView intentionally has a repeating animation.
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.text('収集日未確認'), unverified ? findsOneWidget : findsNothing);
      expect(
          find.text('公式カレンダーを確認'), unverified ? findsOneWidget : findsNothing);
      expect(find.text('推測した日付'), findsNothing);
      expect(find.text('確認済みの収集日'), unverified ? findsNothing : findsOneWidget);
    });
  }
}
