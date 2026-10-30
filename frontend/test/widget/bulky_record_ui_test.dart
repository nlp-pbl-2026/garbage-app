import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/providers/bulky_waste_provider.dart';
import 'package:garbage_app/repositories/bulky_waste_repository.dart';
import 'package:garbage_app/screens/bulky_waste_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

MunicipalityConfig _config(bool island) => island
    ? BulkyWasteRepository.nakajimaConfig()
    : MunicipalityConfig(
        municipalityId: '38201',
        municipalityName: '松山市',
        collectionFrequency: '年6回',
        receptionHours: '申込区分による',
        collectionRules: '申込み後に戸別収集',
        feeStructureType: FeeStructureType.fixed,
        applicationMethod: ApplicationMethod.webForm,
        steps: [],
      );

void main() {
  for (final island in [false, true]) {
    testWidgets('record tab explains local-only management (island: $island)',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      await tester.pumpWidget(ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          municipalityConfigProvider.overrideWith((ref) async => CachedResult(
                data: _config(island),
                isStale: false,
              )),
          bulkyWasteItemsProvider
              .overrideWith((ref, query) async => const CachedResult(
                    data: BulkyWasteItemList(
                      items: [],
                      totalCount: 0,
                      municipalityName: '松山市',
                    ),
                    isStale: false,
                  )),
        ],
        child: const MaterialApp(home: BulkyWasteScreen()),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      final tabLabel = island ? '収集予定メモ' : '申込記録';
      expect(find.text(tabLabel), findsOneWidget);
      await tester.tap(find.text(tabLabel));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(
        find.textContaining(island ? '市の収集状況は取得しません' : '市への申込みや申込状況の取得は行いません'),
        findsOneWidget,
      );
    });
  }
}
