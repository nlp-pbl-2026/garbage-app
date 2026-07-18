import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'constants/strings.dart';
import 'providers/region_provider.dart';
import 'screens/main_screen.dart';
import 'screens/region_selection_screen.dart';

/// 愛媛県ゴミ出しアプリケーションのルートウィジェット
///
/// 地域設定の有無を確認し、初回起動時は地域選択画面、
/// 設定済みの場合はメイン画面を表示する。
class GarbageApp extends ConsumerWidget {
  const GarbageApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: AppStrings.appName,
      theme: ThemeData(
        primarySwatch: Colors.green,
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.green),
        useMaterial3: true,
      ),
      home: const _AppHome(),
    );
  }
}

/// アプリのホーム画面を地域設定の有無で切り替えるウィジェット
class _AppHome extends ConsumerWidget {
  const _AppHome();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionSetting = ref.watch(regionSettingProvider);

    return regionSetting.when(
      data: (setting) {
        if (setting == null) {
          // 地域未設定 → 地域選択画面へ
          return const RegionSelectionScreen();
        }
        // 地域設定済み → メイン画面へ
        return const MainScreen();
      },
      loading: () => const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      ),
      error: (error, stack) => Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                AppStrings.dataLoadError,
                style: const TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  ref.read(regionSettingProvider.notifier).loadSetting();
                },
                child: const Text(AppStrings.retry),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
