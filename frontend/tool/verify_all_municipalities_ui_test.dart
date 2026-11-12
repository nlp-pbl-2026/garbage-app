// Real local district metadata, fake persistence/notifications; no GPS or API.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/municipality_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/settings_provider.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'verify_uwajima_ui_test.dart'
    show ReviewedUwajimaBundle, SelectedUwajima, NoUwajimaOsNotifications;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final files = {
    for (final file in Directory('assets/data')
        .listSync()
        .whereType<File>()
        .where((f) => f.path.endsWith('.json')))
      file.path: file.readAsStringSync(),
  };
  final cities = (jsonDecode(files['assets/data/municipality_catalog.json']!)[
          'municipalities'] as List)
      .cast<Map<String, dynamic>>();
  final data = MunicipalityDataService(bundle: ReviewedUwajimaBundle(files));
  final regions = RegionService(data: data);
  late List<Municipality> municipalities;
  final districtsByCity = <String, List<District>>{};
  setUpAll(() async {
    municipalities = await regions.getMunicipalities('38');
    for (final city in cities) {
      districtsByCity[city['id'] as String] =
          await regions.getDistricts(city['id'] as String);
    }
  });

  for (final city in cities) {
    final id = city['id'] as String;
    testWidgets('$id geographical district can be selected and saved',
        (tester) async {
      // This is a widget test under tool/, outside the analyzer's test/ heuristic.
      // ignore: invalid_use_of_visible_for_testing_member
      SharedPreferences.setMockInitialValues({});
      tester.view.physicalSize = const Size(1200, 2200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final districts = districtsByCity[id]!;
      final selected = SelectedUwajima();
      await tester.pumpWidget(ProviderScope(
          overrides: [
            prefecturesProvider.overrideWith(
                (ref) async => [Prefecture(id: '38', name: '愛媛県')]),
            municipalityDataProvider.overrideWithValue(data),
            municipalitiesProvider('38')
                .overrideWith((ref) async => municipalities),
            districtsProvider(id).overrideWith((ref) async => districts),
            regionCoverageNoticeProvider(id).overrideWith((ref) async => null),
            regionSettingProvider.overrideWith((ref) => selected),
            notificationServiceProvider
                .overrideWithValue(NoUwajimaOsNotifications()),
          ],
          child: const MaterialApp(
              home: RegionSelectionScreen(updateActiveSavedRegion: false))));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('municipality-selector')));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text(city['name'] as String), 200,
          scrollable: find.byType(Scrollable).last);
      await tester.tap(find.text(city['name'] as String));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('district-selector')));
      await tester.pumpAndSettle();
      await tester.tap(find.text(districts.first.displayName).last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('manual-region-button')));
      await tester.pumpAndSettle();
      expect(selected.selected!.municipalityId, id);
      expect(selected.selected!.districtId, districts.first.id);
      expect(selected.selected!.districtName, districts.first.name);
      expect(tester.takeException(), isNull);
    });
  }
}
