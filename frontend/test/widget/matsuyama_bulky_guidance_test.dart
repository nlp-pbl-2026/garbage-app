import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/providers/bulky_waste_provider.dart';
import 'package:garbage_app/repositories/bulky_waste_repository.dart';
import 'package:garbage_app/screens/fee_display_screen.dart';
import 'package:garbage_app/widgets/bulky_waste/application_guide_view.dart';
import 'package:garbage_app/widgets/bulky_waste/external_link_handler.dart';
import 'package:garbage_app/widgets/bulky_waste/item_list_view.dart';

MunicipalityConfig _mainlandConfig() => MunicipalityConfig(
      municipalityId: '38201',
      municipalityName: '松山市',
      collectionFrequency: '年6回',
      receptionHours: '申込区分による',
      collectionRules: '申込み後に戸別収集',
      feeStructureType: FeeStructureType.fixed,
      applicationMethod: ApplicationMethod.webForm,
      webFormUrl:
          'https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/sodaigomi.html',
      steps: [
        ApplicationStep(
          stepNumber: 1,
          title: '申込区分の確認',
          description: '住所の申込区分を確認します。',
        ),
      ],
    );

BulkyWasteItem _freeItem() => BulkyWasteItem(
      id: 1,
      itemName: '自転車',
      category: '粗大ごみ',
      feeAmount: 0,
    );

void main() {
  testWidgets('mainland guide links to the official address-to-group lookup',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ApplicationGuideView(config: _mainlandConfig())),
    ));

    expect(find.text('申込区分A〜Dとは'), findsOneWidget);
    final lookup = tester.widget<ExternalLinkHandler>(
      find.ancestor(
        of: find.text('住所から申込区分を確認'),
        matching: find.byType(ExternalLinkHandler),
      ),
    );
    expect(lookup.webFormUrl,
        'https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/chikukensaku.html');
  });

  testWidgets('island guide shows collection guidance without A-D application',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body:
            ApplicationGuideView(config: BulkyWasteRepository.nakajimaConfig()),
      ),
    ));

    expect(find.text('申込区分A〜Dとは'), findsNothing);
    expect(find.text('中島地域の出し方を確認'), findsOneWidget);
  });

  testWidgets(
      'Matsuyama zero import value is described as free home collection',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: FeeDisplayScreen(item: _freeItem(), config: _mainlandConfig()),
    ));

    expect(find.text('松山・北条地域の戸別収集は無料です。'), findsOneWidget);
    expect(find.text('手数料情報がありません'), findsNothing);
    expect(find.text('0円'), findsNothing);
  });

  testWidgets('item list does not show an unexplained zero yen fee',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        bulkyWasteItemsProvider.overrideWith((ref, query) async => CachedResult(
              data: BulkyWasteItemList(
                items: [_freeItem()],
                totalCount: 1,
                municipalityName: '松山市',
              ),
              isStale: false,
            )),
      ],
      child: MaterialApp(
        home: Scaffold(
          body:
              ItemListView(municipalityId: '38201', config: _mainlandConfig()),
        ),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('戸別収集無料'), findsOneWidget);
    expect(find.text('0円'), findsNothing);
    expect(find.text('手数料↑'), findsNothing);
  });
}
