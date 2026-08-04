/// 通知サービス
///
/// flutter_local_notifications を使用して、
/// ゴミ収集日の前日20:00と当日朝6:00にローカル通知を配信する。
/// 地区のスケジュールに基づき、翌日/当日の収集カテゴリを通知内容に含める。

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/timezone.dart' as tz;
import 'package:timezone/data/latest_all.dart' as tz_data;

import '../models/garbage_item.dart';
import '../models/garbage_category.dart';
import '../models/notification_timing_type.dart';
import 'notification_customization_service.dart';
import 'schedule_service.dart';

/// リマインダー通知設定のキー
const String _reminderEnabledKey = 'reminder_enabled';
const String _districtIdKey = 'notification_district_id';
const String _eveningHourKey = 'notification_evening_hour';
const String _eveningMinuteKey = 'notification_evening_minute';
const String _morningHourKey = 'notification_morning_hour';
const String _morningMinuteKey = 'notification_morning_minute';

/// 通知サービス
///
/// 収集日前日の20:00と当日朝6:00にローカル通知をスケジュールする。
class NotificationService {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  static bool _initialized = false;

  /// 通知プラグインを初期化する
  Future<void> initialize() async {
    if (_initialized) return;

    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));

    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(settings);
    _initialized = true;
  }

  /// リマインダー通知を有効化し、スケジュールを設定する
  Future<void> enableReminder(String districtId) async {
    await initialize();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reminderEnabledKey, true);
    await prefs.setString(_districtIdKey, districtId);

    await scheduleWeeklyNotifications(districtId);
    debugPrint('[NotificationService] リマインダー通知を有効化しました');
  }

  /// リマインダー通知を無効化し、スケジュール済み通知をキャンセルする
  Future<void> disableReminder() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reminderEnabledKey, false);

    await _plugin.cancelAll();
    debugPrint('[NotificationService] リマインダー通知を無効化しました');
  }

  /// リマインダー通知の有効状態を取得する
  Future<bool> isReminderEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_reminderEnabledKey) ?? false;
  }

  /// 今後7日分の通知をスケジュールする
  ///
  /// 各収集日について:
  /// - 前日のカスタム時刻: 「明日は○○ごみの日です」
  /// - 当日のカスタム時刻: 「今日は○○ごみの日です」
  Future<void> scheduleWeeklyNotifications(String districtId) async {
    await initialize();
    await _plugin.cancelAll();

    final scheduleService = ScheduleService();
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    // 保存済みの通知時刻を取得
    final eveningTime = await getEveningTime();
    final morningTime = await getMorningTime();

    // カテゴリフィルタリング用にカスタマイズサービスを取得
    final prefs = await SharedPreferences.getInstance();
    final customizationService = NotificationCustomizationService(prefs);
    final eveningEnabledCategories = await customizationService.getEnabledCategories(
      NotificationTimingType.evening,
    );
    final morningEnabledCategories = await customizationService.getEnabledCategories(
      NotificationTimingType.morning,
    );

    int notificationId = 0;

    for (int i = 0; i < 7; i++) {
      final targetDate = today.add(Duration(days: i));
      final entries = await scheduleService.getScheduleForDate(
        districtId,
        targetDate,
      );

      if (entries.isEmpty) continue;

      // 前日通知: eveningEnabledカテゴリのみフィルタリング
      if (i > 0) {
        final eveningEntries = entries
            .where((e) => eveningEnabledCategories.contains(e.category))
            .toList();

        if (eveningEntries.isNotEmpty) {
          final categoryNames = eveningEntries
              .map((e) => CategoryColors.getLabel(e.category))
              .join('・');

          final eveningBefore = tz.TZDateTime(
            tz.local,
            targetDate.year,
            targetDate.month,
            targetDate.day - 1,
            eveningTime.hour,
            eveningTime.minute,
          );

          if (eveningBefore.isAfter(tz.TZDateTime.now(tz.local))) {
            await _scheduleNotification(
              id: notificationId++,
              title: '明日のゴミ出し',
              body: '明日は${categoryNames}の日です',
              scheduledDate: eveningBefore,
            );
          }
        }
      }

      // 当日通知: morningEnabledカテゴリのみフィルタリング
      final morningEntries = entries
          .where((e) => morningEnabledCategories.contains(e.category))
          .toList();

      if (morningEntries.isNotEmpty) {
        final categoryNames = morningEntries
            .map((e) => CategoryColors.getLabel(e.category))
            .join('・');

        final morningOf = tz.TZDateTime(
          tz.local,
          targetDate.year,
          targetDate.month,
          targetDate.day,
          morningTime.hour,
          morningTime.minute,
        );

        if (morningOf.isAfter(tz.TZDateTime.now(tz.local))) {
          await _scheduleNotification(
            id: notificationId++,
            title: '今日のゴミ出し',
            body: '今日は${categoryNames}の日です',
            scheduledDate: morningOf,
          );
        }
      }
    }

    debugPrint('[NotificationService] ${notificationId}件の通知をスケジュールしました');
  }

  /// 個別の通知をスケジュールする
  Future<void> _scheduleNotification({
    required int id,
    required String title,
    required String body,
    required tz.TZDateTime scheduledDate,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'garbage_reminder',
      'ゴミ出しリマインダー',
      channelDescription: 'ゴミ収集日のリマインダー通知',
      importance: Importance.high,
      priority: Priority.high,
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _plugin.zonedSchedule(
      id,
      title,
      body,
      scheduledDate,
      details,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      matchDateTimeComponents: null,
    );
  }

  /// 通知のリスケジュール（地区変更時やアプリ起動時に呼ぶ）
  Future<void> refreshNotifications() async {
    final enabled = await isReminderEnabled();
    if (!enabled) return;

    final prefs = await SharedPreferences.getInstance();
    final districtId = prefs.getString(_districtIdKey);
    if (districtId == null) return;

    await scheduleWeeklyNotifications(districtId);
  }

  /// 前日通知の時刻を保存する（デフォルト: 20:00）
  Future<void> setEveningTime(int hour, int minute) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_eveningHourKey, hour);
    await prefs.setInt(_eveningMinuteKey, minute);
    await refreshNotifications();
  }

  /// 当日通知の時刻を保存する（デフォルト: 06:00）
  Future<void> setMorningTime(int hour, int minute) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_morningHourKey, hour);
    await prefs.setInt(_morningMinuteKey, minute);
    await refreshNotifications();
  }

  /// 前日通知の時刻を取得する
  Future<({int hour, int minute})> getEveningTime() async {
    final prefs = await SharedPreferences.getInstance();
    final hour = prefs.getInt(_eveningHourKey) ?? 20;
    final minute = prefs.getInt(_eveningMinuteKey) ?? 0;
    return (hour: hour, minute: minute);
  }

  /// 当日通知の時刻を取得する
  Future<({int hour, int minute})> getMorningTime() async {
    final prefs = await SharedPreferences.getInstance();
    final hour = prefs.getInt(_morningHourKey) ?? 6;
    final minute = prefs.getInt(_morningMinuteKey) ?? 0;
    return (hour: hour, minute: minute);
  }
}
