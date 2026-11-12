// Widget checks use local assets and fake persistence; no OS/API operations.
import 'dart:io';
import 'package:intl/date_symbol_data_local.dart';
import 'package:garbage_app/providers/calendar_provider.dart';
import 'package:garbage_app/providers/memo_provider.dart';
import 'package:garbage_app/providers/weather_provider.dart';
import 'package:garbage_app/screens/calendar_screen.dart';
import 'package:garbage_app/services/schedule_service.dart';
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
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/widgets/bulky_waste/application_guide_view.dart';
import '../test/helpers/municipality_assets.dart' show MunicipalityBundle;

class ReviewedUwajimaBundle extends MunicipalityBundle {
  ReviewedUwajimaBundle(super.files);
  @override
  Future<String> loadString(String key, {bool cache = true}) async =>
      files[key] ?? (throw StateError('Missing asset: $key'));
}

class SelectedUwajima extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  SelectedUwajima([RegionSetting? initial]) : super(AsyncValue.data(initial));
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

class NoUwajimaOsNotifications extends NotificationService {
  @override
  Future<void> updateDistrict(String districtId,
      {String municipalityId = '38201'}) async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late MunicipalityDataService data;
  late MunicipalityConfig bulkyConfig;
  late List<Municipality> municipalities;
  late List<District> districts;
  setUpAll(() async {
    await initializeDateFormatting('ja_JP');
    final files = {
      for (final f in Directory('assets/data')
          .listSync()
          .whereType<File>()
          .where((f) => f.path.endsWith('.json')))
        f.path: f.readAsStringSync()
    };
    data = MunicipalityDataService(bundle: ReviewedUwajimaBundle(files));
    final profile = await data.profile('38203', 'uwajima');
    bulkyConfig = MunicipalityConfig.fromJson((profile['bulky_waste']
        as Map<String, dynamic>)['config'] as Map<String, dynamic>);
    final regions = RegionService(data: data);
    municipalities = await regions.getMunicipalities('38');
    districts = await regions.getDistricts('38203');
  });
  // ignore: invalid_use_of_visible_for_testing_member
  setUp(() => SharedPreferences.setMockInitialValues({}));
  void wide(WidgetTester tester) {
    tester.view.physicalSize = const Size(1200, 2200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  testWidgets(
      'region selection displays geographical names and stores the exact ID',
      (tester) async {
    wide(tester);
    final selected = SelectedUwajima();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          prefecturesProvider
              .overrideWith((ref) async => [Prefecture(id: '38', name: '愛媛県')]),
          municipalityDataProvider.overrideWithValue(data),
          municipalitiesProvider('38')
              .overrideWith((ref) async => municipalities),
          districtsProvider('38203').overrideWith((ref) async => districts),
          regionCoverageNoticeProvider('38203')
              .overrideWith((ref) async => null),
          regionSettingProvider.overrideWith((ref) => selected),
          notificationServiceProvider
              .overrideWithValue(NoUwajimaOsNotifications()),
        ],
        child: const MaterialApp(
            home: RegionSelectionScreen(updateActiveSavedRegion: false))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('宇和島市'), 250,
        scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('宇和島市'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    expect(find.text('宇和島地区 → 青葉台'), findsOneWidget);
    for (final internal in ['im-', 'カレンダー番号', '.pdf', '未確認']) {
      expect(find.textContaining(internal), findsNothing);
    }
    await tester.tap(find.text('宇和島地区 → 青葉台'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(selected.selected!.municipalityId, '38203');
    expect(selected.selected!.districtId, '38203-a001');
    expect(selected.selected!.districtName, '宇和島地区 → 青葉台');
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'bulky guide explains direct delivery without a city booking promise',
      (tester) async {
    wide(tester);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ApplicationGuideView(config: bulkyConfig))));
    await tester.pumpAndSettle();
    expect(find.text('宇和島市の粗大ごみの出し方'), findsOneWidget);
    expect(find.text('公式の出し方を確認'), findsOneWidget);
    expect(find.textContaining('直接搬入'), findsWidgets);
    expect(find.textContaining('電話で申し込む'), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('date-specific warning is visible only in its month',
      (tester) async {
    wide(tester);
    final localData = MunicipalityDataService(
        bundle: ReviewedUwajimaBundle({
      for (final f in Directory('assets/data')
          .listSync()
          .whereType<File>()
          .where((f) => f.path.endsWith('.json')))
        f.path: f.readAsStringSync()
    }));
    final district = districts.firstWhere((d) => d.name == '宇和島地区 → 北宇和島町');
    final selected = SelectedUwajima(RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38203',
        municipalityName: '宇和島市',
        districtId: district.id,
        districtName: district.name));
    await tester.pumpWidget(ProviderScope(overrides: [
      municipalityDataProvider.overrideWithValue(localData),
      regionSettingProvider.overrideWith((ref) => selected),
      scheduleServiceProvider.overrideWithValue(ScheduleService(
          data: localData,
          municipalityId: '38203',
          clock: () => DateTime(2026, 9, 29, 9))),
      focusedMonthProvider.overrideWith((ref) => DateTime(2026, 9)),
      selectedDayProvider.overrideWith((ref) => DateTime(2026, 9, 30)),
      memoForDateProvider.overrideWith((ref, date) => null),
      monthlyMemosProvider.overrideWith((ref, month) => <DateTime>{}),
      weatherForecastProvider.overrideWith((ref) async => {}),
    ], child: const MaterialApp(home: CalendarScreen())));
    await tester.pumpAndSettle();
    expect(find.textContaining('PDFの空欄'), findsOneWidget);
    final container =
        ProviderScope.containerOf(tester.element(find.byType(CalendarScreen)));
    container.read(focusedMonthProvider.notifier).state = DateTime(2026, 10);
    await tester.pumpAndSettle();
    expect(find.textContaining('PDFの空欄'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
