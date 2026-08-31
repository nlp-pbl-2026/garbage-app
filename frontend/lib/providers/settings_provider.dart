import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/notification_navigation_handler.dart';
import '../services/notification_service.dart';
import 'calendar_provider.dart';
import 'navigation_provider.dart';
import 'region_provider.dart';

/// NotificationServiceのプロバイダー
///
/// アプリ全体で共有されるNotificationServiceインスタンスを提供する。
final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService();
});

/// アプリ全体で共有する [GlobalKey]<[NavigatorState]>
///
/// `MaterialApp.navigatorKey` へ接続し、通知タップ時のコンテキスト非依存
/// ナビゲーションに使用する（要件 5.1, 5.2）。[notificationNavigationHandlerProvider]
/// と同一のキーを共有する。
final navigatorKeyProvider = Provider<GlobalKey<NavigatorState>>(
  (ref) => GlobalKey<NavigatorState>(),
);

/// 通知タップ時のナビゲーションハンドラのプロバイダー
///
/// [NotificationNavigationHandler] を生成し、通知ペイロード（対象収集日）を
/// 受け取ったときに以下を実行する `onNavigateToCollectionDay` を注入する（要件 5.1, 5.2）:
/// - [selectedDayProvider] を対象収集日で更新（カレンダーの該当日を選択状態にする）
/// - [focusedMonthProvider] を対象収集日の月に合わせる
/// - [selectedTabProvider] をカレンダータブ（[MainTab.calendar]）へ切り替える
///
/// [navigatorKeyProvider] の [GlobalKey] を共有し、`MaterialApp.navigatorKey`
/// と同一のキーを保持する。[NotificationNavigationHandler.notificationResponseCallback]
/// は起動時に [NotificationService.initialize] の `onDidReceiveNotificationResponse`
/// へ接続する（起動フロー: main.dart）。
final notificationNavigationHandlerProvider =
    Provider<NotificationNavigationHandler>((ref) {
  final navigatorKey = ref.watch(navigatorKeyProvider);
  return NotificationNavigationHandler(
    navigatorKey: navigatorKey,
    onNavigateToCollectionDay: (targetDate) {
      // 対象日が復元できた場合はカレンダーの選択日・表示月を更新する。
      if (targetDate != null) {
        ref.read(selectedDayProvider.notifier).state = targetDate;
        ref.read(focusedMonthProvider.notifier).state =
            DateTime(targetDate.year, targetDate.month);
      }
      // カレンダータブへ切り替える（該当日を確認できる画面を開く）。
      ref.read(selectedTabProvider.notifier).state = MainTab.calendar;
    },
  );
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
  ///
  /// 現在無効なら [enable]、有効なら [disable] を呼ぶ。
  /// 有効化を試みた場合はその [EnableResult] を返し、UI（SettingsScreen）が
  /// `permissionDenied` / `requestFailed` に応じたメッセージを提示できるようにする
  /// （要件 2.4, 2.5）。無効化した場合は `null` を返す。
  Future<EnableResult?> toggle() async {
    final currentValue = state.valueOrNull ?? false;
    if (currentValue) {
      await disable();
      return null;
    } else {
      return enable();
    }
  }

  /// リマインダーを有効化する
  ///
  /// 地区IDが設定されている場合に通知をスケジュールする。
  /// [NotificationService.enableReminder] の戻り値 [EnableResult] を伝播し、
  /// [EnableResult.success] のときのみ状態を true にする。
  /// `permissionDenied` / `requestFailed` の場合は権限が付与されていないため
  /// 状態を false のまま保持し、結果を返して UI 側で案内を提示できるようにする
  /// （要件 1.1, 2.4, 2.5）。地区IDが未設定の場合は有効化できないため
  /// 状態を false のまま保持し `null` を返す。
  Future<EnableResult?> enable() async {
    final districtId = _districtId;
    if (districtId == null) {
      // 地区未設定では通知をスケジュールできないため有効化しない。
      state = const AsyncValue.data(false);
      return null;
    }
    try {
      final result = await _notificationService.enableReminder(districtId);
      // 成功時のみ有効状態にする。拒否・送信失敗時は false のまま保持する。
      state = AsyncValue.data(result == EnableResult.success);
      return result;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return null;
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

/// 通知時刻の状態型
///
/// 前日通知（evening）と当日通知（morning）の時・分を保持する。
typedef NotificationTimes = ({
  ({int hour, int minute}) evening,
  ({int hour, int minute}) morning,
});

/// 通知時刻のStateNotifierProvider
///
/// 前日通知・当日通知の配信時刻を [AsyncValue] で管理し、
/// [NotificationService] を通じて SharedPreferences に永続化する。
/// 既存の [reminderEnabledProvider] / [notificationCustomizationProvider]
/// と同一の AsyncValue パターンで実装する（要件 4.2, 4.3）。
final notificationTimesProvider = StateNotifierProvider<
    NotificationTimesNotifier, AsyncValue<NotificationTimes>>((ref) {
  final notificationService = ref.watch(notificationServiceProvider);
  return NotificationTimesNotifier(notificationService);
});

/// 通知時刻を管理する StateNotifier
///
/// 初期化時に SharedPreferences から evening / morning 時刻を読み込み、
/// [AsyncValue.loading] から [AsyncValue.data] へ遷移する。
/// setter は [NotificationService.setEveningTime] / [setMorningTime] を呼び、
/// 保存成功時のみ状態を更新して [SaveTimeResult] を返す。保存失敗時は
/// サービス側で変更前の値へロールバックされるため状態を変更せず
/// [SaveTimeResult.failed] を返し、UI 側でエラーメッセージを提示できるようにする
/// （要件 4.2, 4.3, 4.4）。
class NotificationTimesNotifier
    extends StateNotifier<AsyncValue<NotificationTimes>> {
  final NotificationService _notificationService;

  NotificationTimesNotifier(this._notificationService)
      : super(const AsyncValue.loading()) {
    loadTimes();
  }

  /// SharedPreferences から保存済みの通知時刻を読み込む
  Future<void> loadTimes() async {
    try {
      final evening = await _notificationService.getEveningTime();
      final morning = await _notificationService.getMorningTime();
      if (!mounted) return;
      state = AsyncValue.data((evening: evening, morning: morning));
    } catch (e, st) {
      if (!mounted) return;
      state = AsyncValue.error(e, st);
    }
  }

  /// 前日通知（evening）の時刻を設定する
  ///
  /// 保存成功時のみ状態を更新し [SaveTimeResult.success] を返す。
  /// 保存失敗時は状態を変更せず [SaveTimeResult.failed] を返す（要件 4.2, 4.4）。
  Future<SaveTimeResult> setEveningTime(int hour, int minute) async {
    final result = await _notificationService.setEveningTime(hour, minute);
    if (result == SaveTimeResult.success && mounted) {
      final current = state.valueOrNull;
      if (current != null) {
        state = AsyncValue.data(
          (evening: (hour: hour, minute: minute), morning: current.morning),
        );
      } else {
        await loadTimes();
      }
    }
    return result;
  }

  /// 当日通知（morning）の時刻を設定する
  ///
  /// 保存成功時のみ状態を更新し [SaveTimeResult.success] を返す。
  /// 保存失敗時は状態を変更せず [SaveTimeResult.failed] を返す（要件 4.3, 4.4）。
  Future<SaveTimeResult> setMorningTime(int hour, int minute) async {
    final result = await _notificationService.setMorningTime(hour, minute);
    if (result == SaveTimeResult.success && mounted) {
      final current = state.valueOrNull;
      if (current != null) {
        state = AsyncValue.data(
          (evening: current.evening, morning: (hour: hour, minute: minute)),
        );
      } else {
        await loadTimes();
      }
    }
    return result;
  }
}
