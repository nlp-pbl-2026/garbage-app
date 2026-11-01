import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/models/collection_status.dart';
import 'package:garbage_app/models/waste_guide_result.dart';
import 'package:garbage_app/providers/calendar_provider.dart';
import 'package:garbage_app/providers/municipality_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/settings_provider.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';
import 'package:garbage_app/screens/search_screen.dart';
import 'package:garbage_app/screens/calendar_screen.dart';
import 'package:garbage_app/providers/memo_provider.dart';
import 'package:garbage_app/providers/weather_provider.dart';
import 'package:garbage_app/models/collection_schedule.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/waste_guide_service.dart';
import '../helpers/municipality_assets.dart';
import 'package:garbage_app/services/region_service.dart';

RegionSetting region(String city) => RegionSetting(
    prefectureId: '38',
    prefectureName: '愛媛県',
    municipalityId: city,
    municipalityName: city == '90001' ? '試験市A' : '試験町B',
    districtId: 'same-area',
    districtName: '${city == '90001' ? '試験市A' : '試験町B'}地区');

class SelectedRegion extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  SelectedRegion() : super(AsyncValue.data(region('90001')));
  void change(String city) => state = AsyncValue.data(region(city));
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

class DeferredGuide extends WasteGuideService {
  final calls = <({
    RegionSetting region,
    List<Map<String, String>> clarifications,
    Completer<WasteGuideResult> result
  })>[];
  @override
  Future<WasteGuideResult> classify(
      {required String query,
      required RegionSetting region,
      SearchImageInput? image,
      List<Map<String, String>> clarifications = const [],
      void Function(SearchPipelineStage)? onStageChanged}) {
    final completer = Completer<WasteGuideResult>();
    calls.add(
        (region: region, clarifications: clarifications, result: completer));
    return completer.future;
  }
}

class LocalNotifications extends NotificationService {
  String? municipality;
  @override
  Future<void> updateDistrict(String districtId,
      {String municipalityId = '38201'}) async {
    municipality = municipalityId;
  }
}

class DelayedRegionService extends RegionService {
  final initial = Completer<RegionSetting?>();
  @override
  Future<RegionSetting?> getRegionSetting() => initial.future;
  @override
  Future<void> saveRegionSetting(RegionSetting setting) async {}
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test('slow initial settings load cannot restore the previous municipality after selection', () async {
    final service = DelayedRegionService();
    final notifier = RegionSettingNotifier(service);
    addTearDown(notifier.dispose);
    await notifier.saveSetting(region('90002'));
    service.initial.complete(region('90001'));
    await Future<void>.delayed(Duration.zero);
    expect(notifier.state.valueOrNull?.municipalityId, '90002');
  });

  testWidgets(
      'changing municipality clears follow-up state and discards old in-flight results',
      (tester) async {
    final selected = SelectedRegion();
    final guide = DeferredGuide();
    await tester.pumpWidget(ProviderScope(overrides: [
      regionSettingProvider.overrideWith((ref) => selected),
    ], child: MaterialApp(home: SearchScreen(service: guide))));
    await tester.enterText(find.byType(TextField).first, '試験品');
    await tester.tap(find.text('調べる'));
    await tester.pump();
    guide.calls.last.result.complete(const WasteGuideResult(
        status: 'needs_clarification',
        rewrittenQuery: '試験品',
        followUpQuestion: '古い地域の質問ですか？',
        sources: []));
    await tester.pump();
    expect(find.text('古い地域の質問ですか？'), findsWidgets);
    await tester.enterText(find.byType(TextField).first, 'はい');
    await tester.tap(find.text('回答する'));
    await tester.pump();
    expect(guide.calls.last.clarifications.single['answer'], 'はい');
    selected.change('90002'); // Same district ID, different municipality.
    await tester.pump();
    expect(find.text('古い地域の質問ですか？'), findsNothing);
    guide.calls.last.result.complete(const WasteGuideResult(
        status: 'answered',
        rewrittenQuery: '試験品',
        answer: '古い地域の回答',
        sources: []));
    await tester.pump();
    expect(find.text('古い地域の回答'), findsNothing);
    await tester.enterText(find.byType(TextField).first, '新しい品');
    await tester.tap(find.text('調べる'));
    await tester.pump();
    expect(guide.calls.last.region.municipalityId, '90002');
    expect(guide.calls.last.clarifications, isEmpty);
    guide.calls.last.result.complete(const WasteGuideResult(
        status: 'answered',
        rewrittenQuery: '新しい品',
        answer: '新しい地域の回答',
        sources: []));
    await tester.pump();
    expect(find.text('新しい地域の回答'), findsOneWidget);
  });

  test(
      'calendar providers reload and reset selected day even with a reused district ID',
      () async {
    final selected = SelectedRegion();
    final data = MunicipalityDataService(
        bundle: MunicipalityBundle(multiMunicipalityAssets()));
    final container = ProviderContainer(overrides: [
      regionSettingProvider.overrideWith((ref) => selected),
      municipalityDataProvider.overrideWithValue(data),
    ]);
    addTearDown(container.dispose);
    final month = DateTime(2026, 11);
    expect((await container.read(monthlyScheduleProvider(month).future)).keys,
        [DateTime(2026, 11, 2)]);
    container.read(selectedDayProvider.notifier).state = DateTime(2026, 11, 2);
    selected.change('90002');
    expect(container.read(selectedDayProvider), isNull);
    expect((await container.read(monthlyScheduleProvider(month).future)).keys,
        [DateTime(2026, 11, 3)]);
  });

  testWidgets('manual municipality and area selectors use the common catalog',
      (tester) async {
    tester.view.physicalSize = const Size(1000, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final assets = multiMunicipalityAssets();
    final registry = jsonDecode(assets['90002-registry']!);
    registry['coverage_notice'] = '確認できていない住所は選択対象外です';
    assets['90002-registry'] = jsonEncode(registry);
    final data = MunicipalityDataService(bundle: MunicipalityBundle(assets));
    final selected = SelectedRegion();
    final notifications = LocalNotifications();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          municipalityDataProvider.overrideWithValue(data),
          regionSettingProvider.overrideWith((ref) => selected),
          notificationServiceProvider.overrideWithValue(notifications),
        ],
        child: const MaterialApp(
            home: RegionSelectionScreen(updateActiveSavedRegion: false))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('prefecture-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('愛媛県').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    expect(find.text('試験市A'), findsOneWidget);
    expect(find.text('試験町B'), findsOneWidget);
    expect(find.text('松山市'), findsNothing);
    await tester.tap(find.text('試験町B'));
    await tester.pumpAndSettle();
    expect(find.text('確認できていない住所は選択対象外です'), findsOneWidget);
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('試験町B地区'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(selected.state.valueOrNull?.municipalityId, '90002');
    expect(notifications.municipality, '90002');
    expect(tester.takeException(), isNull);
  });
  testWidgets('calendar displays the registry’s full period including January to March', (tester) async {
    await initializeDateFormatting('ja_JP');
    tester.view.physicalSize = const Size(1000, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final files = multiMunicipalityAssets();
    for (final name in ['90001-registry', '90001-calendar']) {
      final record = jsonDecode(files[name]!);
      record['valid_to'] = '2027-03-31';
      files[name] = jsonEncode(record);
    }
    final data = MunicipalityDataService(bundle: MunicipalityBundle(files));
    await tester.pumpWidget(ProviderScope(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionSettingProvider.overrideWith((ref) => SelectedRegion()),
      focusedMonthProvider.overrideWith((ref) => DateTime(2027, 1)),
      monthlyMemosProvider.overrideWith((ref, month) => <DateTime>{}),
      weatherForecastProvider.overrideWith((ref) async => {}),
    ], child: const MaterialApp(home: CalendarScreen())));
    await tester.pumpAndSettle();
    final calendar = tester.widget<TableCalendar<ScheduleEntry>>(find.byType(TableCalendar<ScheduleEntry>));
    expect(isSameDay(calendar.firstDay, DateTime(2026, 1, 1)), isTrue);
    expect(isSameDay(calendar.lastDay, DateTime(2027, 3, 31)), isTrue);
    expect(calendar.focusedDay.year, 2027);
    expect(calendar.focusedDay.month, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('partial calendar labels unknown streams without claiming no collection', (tester) async {
    await initializeDateFormatting('ja_JP');
    tester.view.physicalSize = const Size(1000, 1800); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final data = MunicipalityDataService(bundle: MunicipalityBundle(partialMunicipalityAssets()));
    await tester.pumpWidget(ProviderScope(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionSettingProvider.overrideWith((ref) => SelectedRegion()),
      focusedMonthProvider.overrideWith((ref) => DateTime(2026, 11)),
      selectedDayProvider.overrideWith((ref) => DateTime(2026, 11, 3)),
      memoForDateProvider.overrideWith((ref, date) => null),
      monthlyMemosProvider.overrideWith((ref, month) => <DateTime>{}),
      weatherForecastProvider.overrideWith((ref) async => {}),
    ], child: const MaterialApp(home: CalendarScreen())));
    await tester.pumpAndSettle();
    expect(find.text('収集日未確認'), findsNWidgets(5));
    expect(find.text('公式カレンダーを確認'), findsOneWidget);
    expect(find.text('確認済みの収集予定はありません。収集日が未確認の区分があります。'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('search shows unknown date and official link instead of a guessed next date', (tester) async {
    final guide = DeferredGuide();
    await tester.pumpWidget(ProviderScope(overrides: [
      regionSettingProvider.overrideWith((ref) => SelectedRegion()),
    ], child: MaterialApp(home: SearchScreen(service: guide))));
    await tester.enterText(find.byType(TextField).first, '試験紙');
    await tester.tap(find.text('調べる')); await tester.pump();
    guide.calls.last.result.complete(const WasteGuideResult(status: 'answered', rewrittenQuery: '試験紙', answer: '紙類です。収集日は未確認です。',
      collectionStatus: CollectionStatus('unverified', message: '未確認', sourceUrl: 'https://example.test/calendar.pdf'),
      nextCollection: NextCollection(date: '2026-11-03', displayDate: '推測した日付', collectionType: '紙類'), sources: []));
    await tester.pump();
    expect(find.text('収集日未確認'), findsOneWidget);
    expect(find.text('公式カレンダーを確認'), findsOneWidget);
    expect(find.text('推測した日付'), findsNothing);
  });

}
