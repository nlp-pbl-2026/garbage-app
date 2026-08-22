/// 粗大ごみ収集通知サービス
///
/// 粗大ごみの申し込み記録に基づき、収集日24時間前に
/// ローカル通知をスケジュールする。
/// 記録作成時・収集日変更時に通知を再スケジュールし、
/// 完了ステータスの記録は通知をキャンセルする。

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/timezone.dart' as tz;
import 'package:timezone/data/latest_all.dart' as tz_data;

import '../models/bulky_waste.dart';

/// 粗大ごみ収集通知サービス
///
/// [ApplicationRecord] に基づき、収集日の24時間前にローカル通知をスケジュールする。
/// - 記録作成時に通知をスケジュール
/// - 収集日変更時に通知を再スケジュール
/// - completed ステータスの記録は通知をキャンセル
/// - 収集日が過去の場合は通知をスケジュールしない
/// - 収集日が24時間以内の場合は即時（収集日時点で）スケジュール
class BulkyWasteNotificationService {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  static bool _initialized = false;

  /// 通知プラグインを初期化する
  ///
  /// 既に初期化済みの場合は何もしない。
  /// タイムゾーンを Asia/Tokyo に設定する。
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

  /// 申し込み記録に対する通知をスケジュールする
  ///
  /// 収集日の24時間前に通知を設定する。
  /// - 収集日が過去の場合はスケジュールしない
  /// - 収集日が24時間以内の場合は収集日当日にスケジュール
  /// - completed ステータスの記録はスケジュールしない
  Future<void> scheduleNotification(ApplicationRecord record) async {
    await initialize();

    // completed ステータスはスケジュールしない
    if (record.status == ApplicationStatus.completed) {
      debugPrint(
          '[BulkyWasteNotification] Record ${record.id} is completed, skipping');
      return;
    }

    final now = tz.TZDateTime.now(tz.local);
    final collectionDateTime = tz.TZDateTime(
      tz.local,
      record.collectionDate.year,
      record.collectionDate.month,
      record.collectionDate.day,
      9, // 収集日の朝9時を基準
      0,
    );

    // 収集日が過去の場合はスケジュールしない
    if (collectionDateTime.isBefore(now)) {
      debugPrint(
          '[BulkyWasteNotification] Record ${record.id} collection date is in the past, skipping');
      return;
    }

    // 通知時刻: 収集日の24時間前
    final notificationTime = collectionDateTime.subtract(
      const Duration(hours: 24),
    );

    // 通知時刻が既に過ぎている場合（24時間以内）は即時スケジュール
    // ただし収集日自体は未来なので、現在時刻の1分後にスケジュール
    final scheduledTime = notificationTime.isBefore(now)
        ? now.add(const Duration(minutes: 1))
        : notificationTime;

    final notificationId = _generateNotificationId(record.id);

    await _scheduleNotification(
      id: notificationId,
      title: '粗大ごみ収集リマインダー',
      body: '明日は「${record.itemName}」の収集日です。準備をお忘れなく。',
      scheduledDate: scheduledTime,
    );

    debugPrint(
        '[BulkyWasteNotification] Scheduled notification for record ${record.id} at $scheduledTime');
  }

  /// 申し込み記録の通知をキャンセルする
  ///
  /// [recordId] に対応する通知をキャンセルする。
  Future<void> cancelNotification(String recordId) async {
    await initialize();

    final notificationId = _generateNotificationId(recordId);
    await _plugin.cancel(notificationId);

    debugPrint(
        '[BulkyWasteNotification] Cancelled notification for record $recordId (id: $notificationId)');
  }

  /// 全アクティブ記録の通知を再スケジュールする
  ///
  /// アプリ起動時や設定変更時に呼び出す。
  /// completed 以外の記録に対して通知をスケジュールし直す。
  Future<void> rescheduleAll(List<ApplicationRecord> records) async {
    await initialize();

    for (final record in records) {
      if (record.status == ApplicationStatus.completed) {
        await cancelNotification(record.id);
      } else {
        await scheduleNotification(record);
      }
    }

    debugPrint(
        '[BulkyWasteNotification] Rescheduled notifications for ${records.length} records');
  }

  /// 文字列IDからユニークな通知IDを生成する
  ///
  /// [id] のハッシュコードを使い、正の整数に変換する。
  /// flutter_local_notifications は int の通知IDを要求するため、
  /// 文字列IDをハッシュして変換する。
  static int _generateNotificationId(String id) {
    // hashCode は負の値を返す可能性があるため、abs() で正の値に変換
    // さらに 31 bit に収める（Android の通知IDは int32 範囲）
    return id.hashCode.abs() % 0x7FFFFFFF;
  }

  /// テスト用: 通知IDの生成メソッドを公開
  @visibleForTesting
  static int generateNotificationId(String id) => _generateNotificationId(id);

  /// 個別の通知をスケジュールする
  Future<void> _scheduleNotification({
    required int id,
    required String title,
    required String body,
    required tz.TZDateTime scheduledDate,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'bulky_waste_reminder',
      '粗大ごみ収集リマインダー',
      channelDescription: '粗大ごみ収集日のリマインダー通知',
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
}
