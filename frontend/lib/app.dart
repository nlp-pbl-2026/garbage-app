import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'constants/strings.dart';
import 'providers/auth_provider.dart';
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

    return MaterialApp(
      title: AppStrings.appName,
      theme: _buildTheme(Brightness.light),
      darkTheme: _buildTheme(Brightness.dark),
      themeMode: themeMode,
      home: const _AppHome(),
    );
  }

  static ThemeData _buildTheme(Brightness brightness) {
    final baseScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF1F6B4F),
      brightness: brightness,
    );
    final scheme = brightness == Brightness.light
        ? baseScheme.copyWith(surface: const Color(0xFFF6F4EE))
        : baseScheme;
    final inputBorder = OutlineInputBorder(
      borderRadius: BorderRadius.circular(15),
      borderSide: BorderSide(color: scheme.outlineVariant),
    );
    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      useMaterial3: true,
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest,
        hintStyle: TextStyle(color: scheme.onSurfaceVariant),
        border: inputBorder,
        enabledBorder: inputBorder,
        focusedBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
      ),
      cardTheme: CardThemeData(
        color: scheme.surfaceContainerLow,
        surfaceTintColor: Colors.transparent,
      ),
      dividerColor: scheme.outlineVariant,
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
