// Widget checks use local assets and fake persistence; no OS/API operations.
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
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/widgets/bulky_waste/application_guide_view.dart';
import '../test/helpers/municipality_assets.dart' show MunicipalityBundle;

class ReviewedKumakogenBundle extends MunicipalityBundle {
  ReviewedKumakogenBundle(super.files);
  @override
  Future<String> loadString(String key, {bool cache = true}) async =>
      files[key] ?? (throw StateError('Missing asset: $key'));
}

class SelectedKumakogen extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  SelectedKumakogen() : super(const AsyncValue.data(null));
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

class NoKumakogenOsNotifications extends NotificationService {
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
    final files = {
      for (final f in Directory('assets/data')
          .listSync()
          .whereType<File>()
          .where((f) => f.path.endsWith('.json')))
        f.path: f.readAsStringSync()
    };
    data = MunicipalityDataService(bundle: ReviewedKumakogenBundle(files));
    final profile = await data.profile('38386', 'citywide');
    bulkyConfig = MunicipalityConfig.fromJson((profile['bulky_waste']
        as Map<String, dynamic>)['config'] as Map<String, dynamic>);
    final regions = RegionService(data: data);
    municipalities = await regions.getMunicipalities('38');
    districts = await regions.getDistricts('38386');
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
    final selected = SelectedKumakogen();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          prefecturesProvider
              .overrideWith((ref) async => [Prefecture(id: '38', name: '愛媛県')]),
          municipalityDataProvider.overrideWithValue(data),
          municipalitiesProvider('38')
              .overrideWith((ref) async => municipalities),
          districtsProvider('38386').overrideWith((ref) async => districts),
          regionCoverageNoticeProvider('38386')
              .overrideWith((ref) async => null),
          regionSettingProvider.overrideWith((ref) => selected),
          notificationServiceProvider
              .overrideWithValue(NoKumakogenOsNotifications()),
        ],
        child: const MaterialApp(
            home: RegionSelectionScreen(updateActiveSavedRegion: false))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('municipality-selector')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('久万高原町'), 250,
        scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('久万高原町'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('district-selector')));
    await tester.pumpAndSettle();
    expect(find.text('久万：久万'), findsOneWidget);
    for (final internal in ['kk-', 'カレンダー番号', '.pdf', '未確認']) {
      expect(find.textContaining(internal), findsNothing);
    }
    await tester.tap(find.text('久万：久万'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('manual-region-button')));
    await tester.pumpAndSettle();
    expect(selected.selected!.municipalityId, '38386');
    expect(selected.selected!.districtId, '38386-01');
    expect(selected.selected!.districtName, '久万：久万');
    expect(tester.takeException(), isNull);
  });

  testWidgets('bulky guide explains carry-in and refers to current reception',
      (tester) async {
    wide(tester);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ApplicationGuideView(config: bulkyConfig))));
    await tester.pumpAndSettle();
    expect(find.text('久万高原町の粗大ごみの出し方'), findsOneWidget);
    expect(find.text('公式の出し方を確認'), findsOneWidget);
    expect(find.textContaining('過去の募集期限は適用しません'), findsOneWidget);
    expect(find.textContaining('電話で申し込む'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
