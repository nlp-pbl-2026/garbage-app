import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/notification_service.dart';
import 'region_provider.dart';

/// NotificationServiceのプロバイダー
///
/// アプリ全体で共有されるNotificationServiceインスタンスを提供する。
final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService();
});

/// リマインダー通知状態のStateNotifierProvider
///
/// リマインダーの有効/無効状態をAsyncValueで管理し、
/// NotificationServiceを通じてSharedPreferencesに永続化する。
final reminderEnabledProvider =
    StateNotifierProvider<ReminderNotifier, AsyncValue<bool>>((ref) {
  final notificationService = ref.watch(notificationServiceProvider);
  final regionSetting = ref.watch(regionSettingProvider).valueOrNull;
  return ReminderNotifier(notificationService, regionSetting?.districtId);
});

/// リマインダー通知状態を管理するStateNotifier
///
/// 収集日前日リマインダーの有効/無効を管理する。
/// 初期化時にSharedPreferencesから保存済み状態を読み込み、
/// 状態変更時にNotificationServiceを通じて永続化する。
class ReminderNotifier extends StateNotifier<AsyncValue<bool>> {
  final NotificationService _notificationService;
  final String? _districtId;

  ReminderNotifier(this._notificationService, this._districtId)
      : super(const AsyncValue.loading()) {
    loadState();
  }

  /// SharedPreferencesから保存済みのリマインダー状態を読み込む
  Future<void> loadState() async {
    try {
      final enabled = await _notificationService.isReminderEnabled();
      state = AsyncValue.data(enabled);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// リマインダーの有効/無効を反転する
  Future<void> toggle() async {
    final currentValue = state.valueOrNull ?? false;
    if (currentValue) {
      await disable();
    } else {
      await enable();
    }
  }

  /// リマインダーを有効化する
  ///
  /// 地区IDが設定されている場合に通知をスケジュールする。
  Future<void> enable() async {
    try {
      final districtId = _districtId;
      if (districtId != null) {
        await _notificationService.enableReminder(districtId);
      }
      state = const AsyncValue.data(true);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// リマインダーを無効化する
  Future<void> disable() async {
    try {
      await _notificationService.disableReminder();
      state = const AsyncValue.data(false);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}
