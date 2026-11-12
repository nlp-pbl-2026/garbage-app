import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/gps_detection_provider.dart';
import 'package:garbage_app/providers/multi_region_provider.dart';
import 'package:garbage_app/providers/navigation_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/settings_provider.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';
import 'package:garbage_app/screens/settings_screen.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/municipality_assets.dart';

final home = RegionSetting(
    prefectureId: '38',
    prefectureName: '愛媛県',
    municipalityId: '38201',
    municipalityName: '松山市',
    districtId: '38201-08',
    districtName: '清水');
final away = RegionSetting(
    prefectureId: '38',
    prefectureName: '愛媛県',
    municipalityId: '38203',
    municipalityName: '宇和島市',
    districtId: '38203-a001',
    districtName: '試験地区');

MunicipalityDataService fixtureData() {
  final files = <String, String>{};
  for (final entry in multiMunicipalityAssets().entries) {
    if (!entry.key.startsWith('90002')) continue;
    files[entry.key.replaceAll('90002', '38203')] = entry.value
        .replaceAll('90002', '38203')
        .replaceAll('試験町B', '宇和島市')
        .replaceAll('same-area', '38203-a001')
        .replaceAll('宇和島市地区', '試験地区');
  }
  final other = jsonDecode(
          multiMunicipalityAssets()['assets/data/municipality_catalog.json']!)[
      'municipalities'][1];
  final catalog =
      jsonDecode(jsonEncode(matsuyamaCatalog())) as Map<String, dynamic>;
  (catalog['municipalities'] as List).add(jsonDecode(jsonEncode(other)
      .replaceAll('90002', '38203')
      .replaceAll('試験町B', '宇和島市')));
  files['assets/data/municipality_catalog.json'] = jsonEncode(catalog);
  files['assets/data/municipality_registry.json'] = jsonEncode({
    'municipality_id': '38201',
    'version': 'test-v1',
    'valid_from': '2026-04-01',
    'valid_to': '2027-03-31',
    'collection_areas': [
      {
        'id': '38201-08',
        'name': '清水',
        'calendar_id': 'c',
        'rule_profile_id': 'matsuyama_hojo'
      }
    ],
  });
  return MunicipalityDataService(bundle: MunicipalityBundle(files));
}

class SavingService extends RegionService {
  SavingService(MunicipalityDataService data, this.current) : super(data: data);
  RegionSetting? current;
  bool fail = false;
  Completer<void>? pending;
  @override
  Future<RegionSetting?> getRegionSetting() async => current;
  @override
  Future<void> saveRegionSetting(RegionSetting setting) async {
    await pending?.future;
    if (fail) throw StateError('test persistence failure');
    await super.saveRegionSetting(setting);
    current = setting;
  }
}

class Notifications extends NotificationService {
  bool fail = false;
  final updates = <String>[];
  @override
  Future<void> updateDistrict(String districtId,
      {String municipalityId = '38201'}) async {
    updates.add('$municipalityId/$districtId');
    if (fail) throw StateError('test notification failure');
  }
}

class DetectedRegion extends StateNotifier<GpsDetectionState>
    implements GpsDetectionNotifier {
  DetectedRegion() : super(const GpsDetectionIdle());
  @override
  Future<void> detectDistrict() async {
    state = GpsDetectionSuccess(DistrictMatchResult(
        districtNumber: 1,
        districtName: away.districtName,
        matchedTown: '試験町',
        region: away));
  }

  @override
  void reset() => state = const GpsDetectionIdle();
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class AppHost extends ConsumerWidget {
  const AppHost({super.key, this.onboarding = false});
  final bool onboarding;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final setting = ref.watch(regionSettingProvider).valueOrNull;
    if (onboarding && setting == null) return const RegionSelectionScreen();
    return Scaffold(
        body: IndexedStack(index: ref.watch(selectedTabProvider), children: [
      Scaffold(
          body: Column(children: [
        Text('検索画面：${setting?.displayName}'),
        TextButton(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                builder: (_) => const RegionSelectionScreen())),
            child: const Text('検索から地域変更')),
      ])),
      const SizedBox(),
      const SettingsScreen(),
    ]));
  }
}

void main() {
  late MunicipalityDataService data;
  late SavingService save;
  late Notifications notifications;
  setUp(() {
    data = fixtureData();
    save = SavingService(data, home);
    notifications = Notifications();
    SharedPreferences.setMockInitialValues({
      'multi_region_migrated': true,
      'region_setting': jsonEncode(home.toJson()),
      'saved_regions': jsonEncode([
        SavedRegion(id: 'home', label: '自宅', setting: home, isActive: true)
            .toJson()
      ]),
    });
  });

  Future<ProviderContainer> start(WidgetTester tester,
      {bool onboarding = false}) async {
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(ProviderScope(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionServiceProvider.overrideWithValue(save),
      notificationServiceProvider.overrideWithValue(notifications),
      gpsDetectionProvider.overrideWith((ref) => DetectedRegion()),
      selectedTabProvider.overrideWith(
          (ref) => onboarding ? MainTab.search : MainTab.settings),
    ], child: MaterialApp(home: AppHost(onboarding: onboarding))));
    await tester.pumpAndSettle();
    return ProviderScope.containerOf(tester.element(find.byType(AppHost)));
  }

  Future<void> open(WidgetTester tester, {bool gps = false}) async {
    final target = find.text(gps ? '現在地から再設定' : '地域を変更').last;
    await tester.ensureVisible(target);
    await tester.tap(target);
    await tester.pumpAndSettle();
  }

  Future<void> selectAway(WidgetTester tester) async {
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('宇和島市'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text(away.districtName));
    await tester.pumpAndSettle();
  }

  void expectSearch(WidgetTester tester, ProviderContainer container,
      RegionSetting expected) {
    expect(find.byType(RegionSelectionScreen), findsNothing);
    expect(container.read(selectedTabProvider), MainTab.search);
    expect(find.text('検索画面：${expected.displayName}'), findsOneWidget);
    expect(tester.takeException(), isNull);
  }

  testWidgets(
      'manual reselection updates the active saved region and returns to search',
      (tester) async {
    final container = await start(tester);
    await open(tester);
    await selectAway(tester);
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, away);
    final active =
        await container.read(multiRegionServiceProvider).getActiveRegion();
    expect(active!.id, 'home');
    expect(active.setting, away);
  });

  testWidgets('manual save still returns when notification rescheduling fails',
      (tester) async {
    notifications.fail = true;
    final container = await start(tester);
    await open(tester);
    await selectAway(tester);
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, away);
    expect(find.textContaining('通知を再設定できませんでした'), findsOneWidget);
    expect(
        (await container.read(multiRegionServiceProvider).getActiveRegion())!
            .setting,
        away);
  });

  testWidgets(
      'GPS confirmation saves and returns even if notification update fails',
      (tester) async {
    notifications.fail = true;
    final container = await start(tester);
    await open(tester, gps: true);
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.tap(find.text('この地域で設定'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expectSearch(tester, container, away);
  });

  testWidgets('recommended region returns to search', (tester) async {
    final container = await start(tester);
    await open(tester);
    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, home);
  });

  testWidgets('a pushed selector without a callback closes itself exactly once',
      (tester) async {
    final container = await start(tester);
    container.read(selectedTabProvider.notifier).state = MainTab.search;
    await tester.pumpAndSettle();
    await tester.tap(find.text('検索から地域変更'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, home);
    expect(find.byType(AppHost), findsOneWidget);
  });

  testWidgets(
      'failed persistence stays on selector, preserves region and allows retry',
      (tester) async {
    final container = await start(tester);
    await open(tester);
    await selectAway(tester);
    save.fail = true;
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(find.byType(RegionSelectionScreen), findsOneWidget);
    expect(find.textContaining('地域を保存できませんでした'), findsOneWidget);
    expect(container.read(regionSettingProvider).valueOrNull, home);
    expect(notifications.updates, isEmpty);
    save.fail = false;
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, away);
  });

  testWidgets('first setup replaces the home screen without popping the app',
      (tester) async {
    save.current = null;
    SharedPreferences.setMockInitialValues({});
    final container = await start(tester, onboarding: true);
    // A previous region can have been removed while the settings tab was open.
    container.read(selectedTabProvider.notifier).state = MainTab.settings;
    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, home);
    final saved =
        await container.read(multiRegionServiceProvider).getSavedRegions();
    expect(saved.single.setting, home);
  });

  testWidgets('failed first setup remains editable and can retry',
      (tester) async {
    save.current = null;
    save.fail = true;
    SharedPreferences.setMockInitialValues({});
    final container = await start(tester, onboarding: true);
    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pumpAndSettle();
    expect(find.byType(RegionSelectionScreen), findsOneWidget);
    expect(find.textContaining('地域を保存できませんでした'), findsOneWidget);
    expect(container.read(regionSettingProvider).valueOrNull, isNull);
    save.fail = false;
    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pumpAndSettle();
    expectSearch(tester, container, home);
  });

  testWidgets(
      'adding a saved region preserves the previous active region and label',
      (tester) async {
    final container = await start(tester);
    await tester.tap(find.text('地区を追加'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), '職場');
    await tester.tap(find.text('次へ'));
    await tester.pumpAndSettle();
    await selectAway(tester);
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(find.byType(RegionSelectionScreen), findsNothing);
    final records =
        await container.read(multiRegionServiceProvider).getSavedRegions();
    expect(records.length, 2);
    expect(records.singleWhere((r) => r.label == '職場').setting, away);
    expect(records.singleWhere((r) => r.isActive).id, 'home');
    expect(container.read(regionSettingProvider).valueOrNull, home);
    expect(container.read(selectedTabProvider), MainTab.settings);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'replacing an unresolved saved region keeps its ID and active home',
      (tester) async {
    final unresolved = RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38201',
        municipalityName: '松山市',
        districtId: 'old-ambiguous',
        districtName: '旧地区');
    SharedPreferences.setMockInitialValues({
      'multi_region_migrated': true,
      'region_setting': jsonEncode(home.toJson()),
      'saved_regions': jsonEncode([
        SavedRegion(id: 'home', label: '自宅', setting: home, isActive: true)
            .toJson(),
        SavedRegion(id: 'work', label: '職場', setting: unresolved).toJson(),
      ]),
    });
    final container = await start(tester);
    await tester.tap(find.text('職場'));
    await tester.pumpAndSettle();
    await selectAway(tester);
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(find.byType(RegionSelectionScreen), findsNothing);
    final records =
        await container.read(multiRegionServiceProvider).getSavedRegions();
    expect(records.length, 2);
    expect(records.singleWhere((r) => r.id == 'work').setting, away);
    expect(records.singleWhere((r) => r.id == 'work').label, '職場');
    expect(records.singleWhere((r) => r.isActive).id, 'home');
    expect(container.read(regionSettingProvider).valueOrNull, home);
    expect(container.read(selectedTabProvider), MainTab.settings);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'leaving while a save is pending never pops the underlying screen',
      (tester) async {
    final container = await start(tester);
    await open(tester);
    save.pending = Completer<void>();
    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pump();
    Navigator.of(tester.element(find.byType(RegionSelectionScreen))).pop();
    await tester.pumpAndSettle();
    save.pending!.complete();
    await tester.pumpAndSettle();
    expect(find.byType(RegionSelectionScreen), findsNothing);
    expect(find.byType(AppHost), findsOneWidget);
    expect(container.read(selectedTabProvider), MainTab.settings);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'GPS result delivered directly to settings also returns to search',
      (tester) async {
    notifications.fail = true;
    final container = await start(tester);
    await container.read(gpsDetectionProvider.notifier).detectDistrict();
    await tester.pumpAndSettle();
    expect(find.text('GPS判定結果'), findsOneWidget);
    await tester.tap(find.text('この地域で設定'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expectSearch(tester, container, away);
    expect(find.textContaining('通知を再設定できませんでした'), findsOneWidget);
  });

  testWidgets(
      'direct settings GPS confirmation stays open on failed persistence',
      (tester) async {
    final container = await start(tester);
    await container.read(gpsDetectionProvider.notifier).detectDistrict();
    await tester.pumpAndSettle();
    save.fail = true;
    await tester.tap(find.text('この地域で設定'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsOneWidget);
    expect(container.read(regionSettingProvider).valueOrNull, home);
    expect(find.textContaining('地域を保存できませんでした'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
