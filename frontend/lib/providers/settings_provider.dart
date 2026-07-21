import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/notification_service.dart';

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
  return ReminderNotifier(notificationService);
});

/// リマインダー通知状態を管理するStateNotifier
///
/// 収集日前日リマインダーの有効/無効を管理する。
/// 初期化時にSharedPreferencesから保存済み状態を読み込み、
/// 状態変更時にNotificationServiceを通じて永続化する。
class ReminderNotifier extends StateNotifier<AsyncValue<bool>> {
  final NotificationService _notificationService;

  ReminderNotifier(this._notificationService)
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
  ///
  /// 現在の状態がtrueならdisable、falseならenableを呼び出す。
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
  /// NotificationServiceのenableReminder()を呼び出し、
  /// 状態をAsyncValue.data(true)に更新する。
  Future<void> enable() async {
    try {
      await _notificationService.enableReminder();
      state = const AsyncValue.data(true);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// リマインダーを無効化する
  ///
  /// NotificationServiceのdisableReminder()を呼び出し、
  /// 状態をAsyncValue.data(false)に更新する。
  Future<void> disable() async {
    try {
      await _notificationService.disableReminder();
      state = const AsyncValue.data(false);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}
