import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'l10n/app_localizations.dart';
import 'providers/auth_provider.dart';
import 'providers/locale_provider.dart';
import 'providers/region_provider.dart';
import 'providers/theme_provider.dart';
import 'screens/login_screen.dart';
import 'screens/main_screen.dart';
import 'screens/region_selection_screen.dart';
import 'widgets/background_monitor_prompt.dart';

/// 愛媛県ゴミ出しアプリケーションのルートウィジェット
class GarbageApp extends ConsumerWidget {
  const GarbageApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final currentLocale = ref.watch(localeProvider);

    return MaterialApp(
      onGenerateTitle: (context) => AppLocalizations.of(context).appName,
      locale: currentLocale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: ThemeData(
        primarySwatch: Colors.green,
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.green),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.green,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      themeMode: themeMode,
      home: const _AppHome(),
    );
  }
}

/// アプリのホーム画面をログイン→地域設定で切り替えるウィジェット
class _AppHome extends ConsumerWidget {
  const _AppHome();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 利用規約の強制表示をスキップし、直接認証チェックへ
    return const _AuthCheck();
  }
}

/// 認証状態チェックウィジェット
///
/// 初回（トークン無し & スキップ未実行）はログイン画面を表示。
/// ログイン済みまたはスキップ後は地域チェックへ。
class _AuthCheck extends ConsumerWidget {
  const _AuthCheck();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);

    return authState.when(
      data: (state) {
        if (state.isLoggedIn || state.hasSkippedLogin) {
          // ログイン済み or スキップ済み → 通常フローへ
          return const _RegionCheck();
        }
        // 未ログイン & 未スキップ → ログイン画面を表示
        return const LoginScreen();
      },
      // 初回ロード中（トークン確認中）
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (_, __) => const _RegionCheck(),
    );
  }
}

/// 地域設定チェックウィジェット
class _RegionCheck extends ConsumerWidget {
  const _RegionCheck();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionSetting = ref.watch(regionSettingProvider);

    return regionSetting.when(
      data: (setting) {
        if (setting == null) {
          return const RegionSelectionScreen();
        }
        return const BackgroundMonitorPrompt(
          child: MainScreen(),
        );
      },
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (error, stack) => Scaffold(
        body: Center(
          child: Builder(
            builder: (context) => Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  AppLocalizations.of(context).dataLoadError,
                  style: const TextStyle(fontSize: 16),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    ref.read(regionSettingProvider.notifier).loadSetting();
                  },
                  child: Text(AppLocalizations.of(context).retry),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
