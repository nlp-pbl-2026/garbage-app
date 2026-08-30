import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/auth_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/screens/login_screen.dart';
import 'package:garbage_app/screens/region_selection_screen.dart';

void main() {
  testWidgets('登録なしの導線を主表示し、アカウントフォームは必要時だけ開く', (tester) async {
    final notifier = _FakeAuthStateNotifier();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authStateProvider.overrideWith((ref) => notifier),
        ],
        child: const MaterialApp(home: LoginScreen()),
      ),
    );

    expect(find.byKey(const Key('continue-without-login')), findsOneWidget);
    expect(find.text('ログインせず、すぐ試す'), findsOneWidget);
    expect(find.byType(TextFormField), findsNothing);

    await tester.tap(find.byKey(const Key('account-form-toggle')));
    await tester.pumpAndSettle();
    expect(find.byType(TextFormField), findsNWidgets(2));

    await tester.tap(find.byKey(const Key('account-form-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('continue-without-login')));
    await tester.pump();
    expect(notifier.skipCount, 1);
  });

  testWidgets('松山市・清水地区をワンタップで保存できる', (tester) async {
    final notifier = _FakeRegionSettingNotifier();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          prefecturesProvider.overrideWith(
            (ref) async => [Prefecture(id: '38', name: '愛媛県')],
          ),
          regionSettingProvider.overrideWith((ref) => notifier),
        ],
        child: const MaterialApp(home: RegionSelectionScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('都道府県から選ぶ'), findsOneWidget);
    expect(find.byKey(const Key('prefecture-selector')), findsOneWidget);
    expect(find.byKey(const Key('quick-region-button')), findsOneWidget);

    await tester.tap(find.byKey(const Key('quick-region-button')));
    await tester.pump();

    expect(notifier.saved?.prefectureName, '愛媛県');
    expect(notifier.saved?.municipalityName, '松山市');
    expect(notifier.saved?.districtId, '38201-08');
    expect(notifier.saved?.districtName, '清水');
  });

  testWidgets('都道府県の選択肢として愛媛県を表示する', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          regionSettingProvider.overrideWith(
            (ref) => _FakeRegionSettingNotifier(),
          ),
        ],
        child: const MaterialApp(home: RegionSelectionScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('prefecture-selector')));
    await tester.pumpAndSettle();

    expect(find.text('都道府県を選択'), findsOneWidget);
    expect(find.text('愛媛県'), findsWidgets);
  });
}

class _FakeAuthStateNotifier extends StateNotifier<AsyncValue<AuthState>>
    implements AuthStateNotifier {
  _FakeAuthStateNotifier() : super(const AsyncValue.data(AuthState.loggedOut));

  int skipCount = 0;

  @override
  Future<void> skipLogin() async {
    skipCount++;
    state = const AsyncValue.data(AuthState.skipped);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeRegionSettingNotifier
    extends StateNotifier<AsyncValue<RegionSetting?>>
    implements RegionSettingNotifier {
  _FakeRegionSettingNotifier() : super(const AsyncValue.data(null));

  RegionSetting? saved;

  @override
  Future<void> saveSetting(RegionSetting setting) async {
    saved = setting;
    state = AsyncValue.data(setting);
  }

  @override
  RegionValidationResult validate({
    String? prefectureId,
    String? municipalityId,
    String? districtId,
  }) {
    return RegionValidationResult.validate(
      prefectureId: prefectureId,
      municipalityId: municipalityId,
      districtId: districtId,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
