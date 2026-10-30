import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/theme_provider.dart';
import 'package:garbage_app/screens/settings_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _SelectedRegion extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  _SelectedRegion()
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

void main() {
  testWidgets('current region card is display-only and theme follows the OS',
      (tester) async {
    SharedPreferences.setMockInitialValues({'dark_mode': 'system'});
    tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
    addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
    tester.view.physicalSize = const Size(900, 1500);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(ProviderScope(
      overrides: [
        regionSettingProvider.overrideWith((ref) => _SelectedRegion()),
      ],
      child: Consumer(builder: (context, ref, child) {
        return MaterialApp(
          theme: ThemeData.light(),
          darkTheme: ThemeData.dark(),
          themeMode: ref.watch(themeModeProvider),
          home: const SettingsScreen(),
        );
      }),
    ));
    await tester.pump();

    final regionCard = find.ancestor(
      of: find.text('松山市 清水'),
      matching: find.byType(Card),
    );
    expect(regionCard, findsOneWidget);
    expect(
      find.descendant(
          of: regionCard, matching: find.byIcon(Icons.chevron_right)),
      findsNothing,
    );
    expect(find.text('変更は下の「地域を変更」から'), findsOneWidget);
    expect(Theme.of(tester.element(find.byType(SettingsScreen))).brightness,
        Brightness.dark);

    await tester.scrollUntilVisible(
      find.textContaining('端末の設定に合わせる'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('端末の設定に合わせる（現在: ダーク）'), findsOneWidget);

    tester.platformDispatcher.platformBrightnessTestValue = Brightness.light;
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(Theme.of(tester.element(find.byType(SettingsScreen))).brightness,
        Brightness.light);
    expect(find.text('端末の設定に合わせる（現在: ライト）'), findsOneWidget);
  });
}
