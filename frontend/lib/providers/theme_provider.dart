import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// テーマモード永続化キー
const _kThemeModeKey = 'dark_mode';

/// テーマモード管理用 StateNotifier
///
/// SharedPreferences で「dark_mode」設定を永続化し、
/// light / dark の2モードを管理する。
class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier() : super(ThemeMode.light) {
    _loadThemeMode();
  }

  /// SharedPreferences からテーマモードを読み込む
  Future<void> _loadThemeMode() async {
    final prefs = await SharedPreferences.getInstance();
    final value = prefs.getString(_kThemeModeKey);
    if (value != null) {
      state = _themeModeFromString(value);
    }
  }

  /// テーマモードを直接設定する
  Future<void> setThemeMode(ThemeMode mode) async {
    state = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kThemeModeKey, _themeModeToString(mode));
  }

  /// light ↔ dark の切り替え
  Future<void> toggle() async {
    final next = state == ThemeMode.light ? ThemeMode.dark : ThemeMode.light;
    await setThemeMode(next);
  }

  /// ThemeMode → 永続化用文字列
  static String _themeModeToString(ThemeMode mode) {
    return switch (mode) {
      ThemeMode.light => 'light',
      ThemeMode.dark => 'dark',
      _ => 'light',
    };
  }

  /// 永続化用文字列 → ThemeMode
  static ThemeMode _themeModeFromString(String value) {
    return switch (value) {
      'dark' => ThemeMode.dark,
      _ => ThemeMode.light,
    };
  }
}

/// テーマモード Provider
///
/// デフォルトは ThemeMode.light。
final themeModeProvider =
    StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  return ThemeModeNotifier();
});
