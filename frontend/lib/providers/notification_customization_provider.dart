import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/category_notification_setting.dart';
import '../models/garbage_item.dart';
import '../models/notification_timing_type.dart';
import '../services/notification_customization_service.dart';
import '../services/notification_service.dart';
import 'settings_provider.dart';

/// カテゴリ別通知設定の状態型
typedef CategorySettingsMap = Map<GarbageCategory, CategoryNotificationSetting>;

/// NotificationCustomizationServiceのプロバイダー
///
/// アプリ起動時にSharedPreferencesを取得してNotificationCustomizationServiceを初期化し、
/// ProviderScopeのoverridesで実インスタンスを設定する。
/// 未初期化状態でアクセスされた場合はUnimplementedErrorをスローする。
final notificationCustomizationServiceProvider =
    Provider<NotificationCustomizationService>((ref) {
  throw UnimplementedError(
    'notificationCustomizationServiceProvider must be overridden with an initialized NotificationCustomizationService instance',
  );
});

/// カテゴリ別通知設定のStateNotifierProvider
///
/// 各GarbageCategoryに対する前日通知・当日通知のON/OFF状態をAsyncValueで管理する。
/// 初期化時にSharedPreferencesから設定を読み込み、トグル操作で永続化と通知再スケジュールを行う。
final notificationCustomizationProvider = StateNotifierProvider<
    NotificationCustomizationNotifier, AsyncValue<CategorySettingsMap>>((ref) {
  final customizationService =
      ref.watch(notificationCustomizationServiceProvider);
  final notificationService = ref.watch(notificationServiceProvider);
  return NotificationCustomizationNotifier(
      customizationService, notificationService);
});

/// カテゴリ別通知設定を管理するStateNotifier
///
/// 初期化時にSharedPreferencesから設定を読み込み、AsyncValue.loadingからAsyncValue.dataへ遷移する。
/// toggle操作で設定を反転・永続化し、NotificationService.refreshNotifications()で通知を再スケジュールする。
/// エラー時はデフォルト全ON状態にフォールバックする。
class NotificationCustomizationNotifier
    extends StateNotifier<AsyncValue<CategorySettingsMap>> {
  final NotificationCustomizationService _customizationService;
  final NotificationService _notificationService;

  NotificationCustomizationNotifier(
    this._customizationService,
    this._notificationService,
  ) : super(const AsyncValue.loading()) {
    _loadSettings();
  }

  /// SharedPreferencesから設定を読み込む
  ///
  /// 読み込み成功時はAsyncValue.dataへ遷移する。
  /// 読み込み失敗時はデフォルト全ON状態にフォールバックし、AsyncValue.dataへ遷移する。
  Future<void> _loadSettings() async {
    try {
      final settings = await _customizationService.loadAllSettings();
      if (!mounted) return;
      state = AsyncValue.data(settings);
    } catch (e, st) {
      debugPrint(
          '[NotificationCustomizationNotifier] 設定読み込みエラー: $e\n$st');
      if (!mounted) return;
      // エラー時はデフォルト全ON状態にフォールバック
      state = AsyncValue.data(_buildDefaultSettings());
    }
  }

  /// 指定カテゴリ・タイミングの設定をトグルする
  ///
  /// 現在の値を反転し、永続化した後にNotificationService.refreshNotifications()を呼び出す。
  /// 永続化失敗時はUI状態をロールバックする。
  Future<void> toggle(
    GarbageCategory category,
    NotificationTimingType timing,
  ) async {
    final currentSettings = state.valueOrNull;
    if (currentSettings == null) return;

    final currentSetting = currentSettings[category];
    if (currentSetting == null) return;

    // 現在の値を反転
    final bool newValue;
    switch (timing) {
      case NotificationTimingType.evening:
        newValue = !currentSetting.eveningEnabled;
        break;
      case NotificationTimingType.morning:
        newValue = !currentSetting.morningEnabled;
        break;
    }

    // 楽観的UI更新
    final updatedSetting = timing == NotificationTimingType.evening
        ? currentSetting.copyWith(eveningEnabled: newValue)
        : currentSetting.copyWith(morningEnabled: newValue);

    final updatedSettings =
        Map<GarbageCategory, CategoryNotificationSetting>.from(currentSettings);
    updatedSettings[category] = updatedSetting;
    state = AsyncValue.data(updatedSettings);

    try {
      // 永続化
      await _customizationService.saveSetting(category, timing, newValue);
      // 通知を再スケジュール
      await _notificationService.refreshNotifications();
    } catch (e, st) {
      debugPrint(
          '[NotificationCustomizationNotifier] トグル保存エラー: $e\n$st');
      // 永続化失敗時はロールバック
      if (!mounted) return;
      state = AsyncValue.data(currentSettings);
    }
  }

  /// デフォルト全ON状態の設定マップを生成する
  CategorySettingsMap _buildDefaultSettings() {
    final Map<GarbageCategory, CategoryNotificationSetting> defaults = {};
    for (final category in GarbageCategory.values) {
      defaults[category] = CategoryNotificationSetting(
        category: category,
        eveningEnabled: true,
        morningEnabled: true,
      );
    }
    return defaults;
  }
}
