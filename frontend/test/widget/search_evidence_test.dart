import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/models/waste_guide_result.dart';
import 'package:garbage_app/providers/auth_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/screens/search_screen.dart';
import 'package:garbage_app/services/waste_guide_service.dart';

class _TestRegion extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  _TestRegion()
      : super(AsyncValue.data(RegionSetting(
          prefectureId: '38',
          prefectureName: '愛媛県',
          municipalityId: '38201',
          municipalityName: '松山市',
          districtId: '38201-08',
          districtName: '清水',
        )));

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _TestAuth extends StateNotifier<AsyncValue<AuthState>>
    implements AuthStateNotifier {
  _TestAuth() : super(const AsyncValue.data(AuthState.skipped));

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _TestGuide extends WasteGuideService {
  @override
  Future<WasteGuideResult> classify({
    required String query,
    required RegionSetting region,
    SearchImageInput? image,
    List<Map<String, String>> clarifications = const [],
    void Function(SearchPipelineStage stage)? onStageChanged,
  }) async {
    return const WasteGuideResult(
      status: 'answered',
      answer: '清水地区の収集日です。',
      rewrittenQuery: 'アルミ缶',
      sources: [GuideSource(title: '松山市の公式資料', snippet: '缶の分別')],
    );
  }
}

void main() {
  testWidgets('search evidence expands without a missing Material exception',
      (tester) async {
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        regionSettingProvider.overrideWith((ref) => _TestRegion()),
        authStateProvider.overrideWith((ref) => _TestAuth()),
      ],
      child: MaterialApp(home: SearchScreen(service: _TestGuide())),
    ));
    await tester.enterText(find.byType(TextField).first, 'アルミ缶');
    await tester.tap(find.text('調べる'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('確認に使った情報'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('確認に使った情報'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('松山市の公式資料'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
