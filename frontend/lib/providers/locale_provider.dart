import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/notification_service.dart';

/// 現在のアプリロケールを管理するStateNotifierProvider
///
/// SharedPreferencesから初期値を読み込み、変更時に永続化する。
/// MaterialAppがこのプロバイダーを監視し、ロケール変更で即座に再描画する。
final localeProvider = StateNotifierProvider<LocaleNotifier, Locale>((ref) {
  return LocaleNotifier();
});

/// アプリのロケール状態を管理するStateNotifier
///
/// 初期状態はJapanese (ja)。
/// [initialize] で SharedPreferences から保存済み言語コードを読み込み、
/// 未保存の場合はシステムロケールを検出してサポート言語にマッチさせる。
/// [setLocale] で言語変更と永続化を行う（同一ロケールの場合はスキップ）。
class LocaleNotifier extends StateNotifier<Locale> {
  LocaleNotifier() : super(const Locale('ja'));

  /// SharedPreferencesに保存するキー名
  static const String _storageKey = 'language_code';

  /// サポートする言語コード一覧
  static const List<String> supportedCodes = ['ja', 'en', 'pt', 'zh', 'vi'];

  /// 初期化: SharedPreferencesから読み込み or システムロケール検出
  ///
  /// 1. 保存済みコードが有効 → そのロケールを適用
  /// 2. 保存済みコードが無効 → "ja"で上書きして適用
  /// 3. 保存なし → システムロケールを検出し、resolveLocaleで解決して適用
  Future<void> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    final storedCode = prefs.getString(_storageKey);

    if (storedCode != null) {
      // 保存済みコードが存在する場合
      if (supportedCodes.contains(storedCode)) {
        // 有効なコード → 適用
        state = Locale(storedCode);
      } else {
        // 無効なコード → "ja"で上書きして適用
        await prefs.setString(_storageKey, 'ja');
        state = const Locale('ja');
      }
    } else {
      // 保存なし → システムロケールを検出
      Locale systemLocale;
      try {
        systemLocale = WidgetsBinding.instance.platformDispatcher.locale;
      } catch (_) {
        // システムロケール検出失敗 → フォールバック
        systemLocale = const Locale('ja');
      }
      final resolved = resolveLocale(systemLocale);
      state = resolved;
    }
  }

  /// ロケール変更 + 永続化
  ///
  /// 現在のロケールと同じ場合は何もしない（冪等性）。
  /// 異なる場合はSharedPreferencesに保存し、状態を更新する。
  /// 通知スケジュールを新しい言語で再設定する。
  Future<void> setLocale(Locale locale) async {
    if (locale.languageCode == state.languageCode) {
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, locale.languageCode);
    state = locale;

    // 言語変更時に通知を新しい言語で再スケジュールする
    final notificationService = NotificationService();
    await notificationService.refreshNotifications();
  }

  /// ロケール解決ロジック（システムロケール → サポート言語マッチング）
  ///
  /// 言語コードのプレフィックス（"-"または"_"より前の部分）を抽出し、
  /// サポート言語リストに含まれていればそのLocaleを返す。
  /// 含まれていなければJapanese (ja) にフォールバックする。
  Locale resolveLocale(Locale systemLocale) {
    final code = systemLocale.languageCode.split('-').first.split('_').first;

    if (supportedCodes.contains(code)) {
      return Locale(code);
    }

    return const Locale('ja');
  }
}
