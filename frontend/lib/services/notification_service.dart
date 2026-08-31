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

import '../models/collection_schedule.dart';
import '../models/garbage_category.dart';
import '../models/garbage_item.dart';
import '../models/notification_timing_type.dart';
import 'notification_customization_service.dart';
import 'schedule_service.dart';

/// リマインダー有効化の結果
///
/// UI/Provider 層はこの結果に応じてメッセージ提示を行う（副作用の分離）。
enum EnableResult {
  /// 権限付与＋スケジュール完了
  success,

  /// ユーザーが権限を拒否（OS設定画面への案内が必要）
  permissionDenied,

  /// 権限リクエスト送信自体が失敗
  requestFailed,
}

/// 通知時刻保存の結果
enum SaveTimeResult {
  /// 保存成功
  success,

  /// 保存失敗（変更前の値へロールバック済み、エラー提示が必要）
  failed,
}

/// OS 権限リクエストの結果
///
/// リクエスト送信失敗（requestError）と拒否（denied）を区別する。
enum PermissionOutcome {
  /// 権限が付与された
  granted,

  /// ユーザーが権限を拒否した
  denied,

  /// 権限リクエストの送信自体が失敗した
  requestError,
}

/// スケジュール対象の通知1件分の計算結果（純粋データ）。
///
/// 副作用（`zonedSchedule` 呼び出し）を伴わない純粋な計算結果として、
/// ScheduleWindow の計算ロジックが返す値オブジェクト。テスト時はこの
/// リストを検証することで、スケジューリング計算の正しさを決定的に確認できる。
class PlannedNotification {
  /// 通知タイトル（例: 「明日のゴミ出し」）
  final String title;

  /// 通知本文（例: 「明日は可燃ごみ・資源ごみの日です」）
  final String body;

  /// 配信予定時刻（ローカルタイムゾーン）
  final tz.TZDateTime scheduledDate;

  /// 通知タップ時のペイロード。対象収集日の ISO8601 文字列。
  final String payload;

  /// この通知が EveningNotification（前日通知）なら true、
  /// MorningNotification（当日通知）なら false。
  final bool isEvening;

  const PlannedNotification({
    required this.title,
    required this.body,
    required this.scheduledDate,
    required this.payload,
    required this.isEvening,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is PlannedNotification &&
          runtimeType == other.runtimeType &&
          title == other.title &&
          body == other.body &&
          scheduledDate == other.scheduledDate &&
          payload == other.payload &&
          isEvening == other.isEvening;

  @override
  int get hashCode =>
      Object.hash(title, body, scheduledDate, payload, isEvening);

  @override
  String toString() => 'PlannedNotification(title: $title, body: $body, '
      'scheduledDate: $scheduledDate, payload: $payload, isEvening: $isEvening)';
}

/// リマインダー通知設定のキー
const String _reminderEnabledKey = 'reminder_enabled';
const String _districtIdKey = 'notification_district_id';
const String _eveningHourKey = 'notification_evening_hour';
const String _eveningMinuteKey = 'notification_evening_minute';
const String _morningHourKey = 'notification_morning_hour';
const String _morningMinuteKey = 'notification_morning_minute';

/// 通知設定の既定値（要件 4.1, 6.5）
const bool _defaultReminderEnabled = false;
const int _defaultEveningHour = 20;
const int _defaultEveningMinute = 0;
const int _defaultMorningHour = 6;
const int _defaultMorningMinute = 0;

/// 通知サービス
///
/// 収集日前日の20:00と当日朝6:00にローカル通知をスケジュールする。
class NotificationService {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  static bool _initialized = false;

  /// 現在時刻を返す注入可能なクロック。
  ///
  /// テスト時に固定時刻を注入し、過去時刻スキップ（要件3.5）などを
  /// 決定的に検証できるようにする。既定では `DateTime.now` を使用する。
  final DateTime Function() _now;

  /// [now] に現在時刻を返す関数を注入できる。省略時は `DateTime.now`。
  NotificationService({DateTime Function()? now}) : _now = now ?? DateTime.now;

  /// 通知プラグインを初期化する
  ///
  /// [onDidReceiveNotificationResponse] を指定すると、フォアグラウンド/バック
  /// グラウンドからの通知タップ応答が `flutter_local_notifications` の
  /// `onDidReceiveNotificationResponse` に接続される（要件 5.1）。通常は
  /// [NotificationNavigationHandler.notificationResponseCallback] を渡す。
  /// 省略した場合はタップ応答コールバックを接続しない（既存呼び出しとの後方互換）。
  Future<void> initialize({
    DidReceiveNotificationResponseCallback? onDidReceiveNotificationResponse,
  }) async {
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

    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: onDidReceiveNotificationResponse,
    );
    _initialized = true;
  }

  /// リマインダー通知を有効化し、スケジュールを設定する。
  ///
  /// OS 権限をリクエストし、その結果に応じて [EnableResult] を返す（副作用の分離）。
  /// - [PermissionOutcome.requestError]: リクエスト送信自体が失敗。ReminderEnabledFlag は
  ///   false のまま保持し、[EnableResult.requestFailed] を返す（要件 2.2）。
  /// - [PermissionOutcome.denied]: ユーザーが拒否。ReminderEnabledFlag は false のまま
  ///   保持し、[EnableResult.permissionDenied] を返す（要件 2.4）。
  /// - [PermissionOutcome.granted]: ReminderEnabledFlag=true と District_ID を保存し、
  ///   ScheduleWindow 内の通知をスケジュールして [EnableResult.success] を返す
  ///   （要件 1.1, 1.2, 2.3）。
  Future<EnableResult> enableReminder(String districtId) async {
    await initialize();

    final outcome = await _requestPermission();
    switch (outcome) {
      case PermissionOutcome.requestError:
        // リクエスト送信失敗。有効化を中止し flag は false のまま（要件 2.2）。
        debugPrint('[NotificationService] 権限リクエスト送信に失敗、有効化を中止しました');
        return EnableResult.requestFailed;
      case PermissionOutcome.denied:
        // ユーザーが拒否。有効化を中止し flag は false のまま（要件 2.4）。
        debugPrint('[NotificationService] 通知権限が拒否されたため、有効化を中止しました');
        return EnableResult.permissionDenied;
      case PermissionOutcome.granted:
        // 付与された場合のみ flag=true と districtId を保存しスケジュールする（要件 1.1, 1.2, 2.3）。
        await _writeReminderEnabled(true);
        await _writeDistrictId(districtId);

        await scheduleWeeklyNotifications(districtId);
        debugPrint('[NotificationService] リマインダー通知を有効化しました');
        return EnableResult.success;
    }
  }

  /// リマインダー通知を無効化し、スケジュール済み通知をキャンセルする
  Future<void> disableReminder() async {
    await _writeReminderEnabled(false);

    await _plugin.cancelAll();
    debugPrint('[NotificationService] リマインダー通知を無効化しました');
  }

  /// リマインダー通知の有効状態を取得する
  ///
  /// SharedPreferences からの読み込みに失敗した場合は、既定値
  /// （`reminder_enabled=false`）として動作する（要件 6.5）。
  Future<bool> isReminderEnabled() async {
    return _readReminderEnabled();
  }

  // --- SharedPreferences 永続化スキーマのアクセサ（要件 4.1, 6.1, 6.5） ---
  //
  // 通知設定の全キーの読み書きを集約する。読み込み系は例外を捕捉し、
  // 失敗時は既定値へフォールバックする。特に ReminderEnabledFlag は
  // 読み込み失敗時に false として動作する（要件 6.5）。

  /// ReminderEnabledFlag を読み込む。失敗時は既定値 false（要件 6.5）。
  Future<bool> _readReminderEnabled() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(_reminderEnabledKey) ?? _defaultReminderEnabled;
    } catch (e) {
      debugPrint('[NotificationService] reminder_enabled の読み込みに失敗: $e');
      return _defaultReminderEnabled;
    }
  }

  /// ReminderEnabledFlag を保存する。
  Future<void> _writeReminderEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reminderEnabledKey, enabled);
  }

  /// 選択中の District_ID を読み込む。失敗時は null。
  Future<String?> _readDistrictId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(_districtIdKey);
    } catch (e) {
      debugPrint('[NotificationService] notification_district_id の読み込みに失敗: $e');
      return null;
    }
  }

  /// 選択中の District_ID を保存する。
  Future<void> _writeDistrictId(String districtId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_districtIdKey, districtId);
  }

  /// EveningNotification 時刻を読み込む。失敗・未設定時は既定 20:00（要件 4.1）。
  Future<({int hour, int minute})> _readEveningTime() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final hour = prefs.getInt(_eveningHourKey) ?? _defaultEveningHour;
      final minute = prefs.getInt(_eveningMinuteKey) ?? _defaultEveningMinute;
      return (hour: hour, minute: minute);
    } catch (e) {
      debugPrint('[NotificationService] evening 時刻の読み込みに失敗: $e');
      return (hour: _defaultEveningHour, minute: _defaultEveningMinute);
    }
  }

  /// EveningNotification 時刻を保存する。
  Future<void> _writeEveningTime(int hour, int minute) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_eveningHourKey, hour);
    await prefs.setInt(_eveningMinuteKey, minute);
  }

  /// MorningNotification 時刻を読み込む。失敗・未設定時は既定 06:00（要件 4.1）。
  Future<({int hour, int minute})> _readMorningTime() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final hour = prefs.getInt(_morningHourKey) ?? _defaultMorningHour;
      final minute = prefs.getInt(_morningMinuteKey) ?? _defaultMorningMinute;
      return (hour: hour, minute: minute);
    } catch (e) {
      debugPrint('[NotificationService] morning 時刻の読み込みに失敗: $e');
      return (hour: _defaultMorningHour, minute: _defaultMorningMinute);
    }
  }

  /// MorningNotification 時刻を保存する。
  Future<void> _writeMorningTime(int hour, int minute) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_morningHourKey, hour);
    await prefs.setInt(_morningMinuteKey, minute);
  }

  /// OS に対して通知権限をリクエストする（差し替え可能な内部フック）。
  ///
  /// iOS/Android の `flutter_local_notifications` 権限 API をラップし、
  /// 付与（granted）・拒否（denied）・送信失敗（requestError）を区別して返す（要件 2.1）。
  /// テスト時はサブクラスやフェイクで差し替えられるよう private の内部フックとする。
  ///
  /// - Android: [AndroidFlutterLocalNotificationsPlugin.requestNotificationsPermission]
  /// - iOS: [IOSFlutterLocalNotificationsPlugin.requestPermissions]
  ///
  /// リクエスト送信自体が失敗（例外）した場合は [PermissionOutcome.requestError] を返し、
  /// 付与可否が確定した場合は [PermissionOutcome.granted] / [PermissionOutcome.denied] を返す。
  /// プラットフォーム実装が解決できない、または結果が不明（null）な場合は
  /// 拒否として扱い、有効化を安全側に倒す。
  Future<PermissionOutcome> _requestPermission() async {
    try {
      final androidImpl = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      if (androidImpl != null) {
        final granted = await androidImpl.requestNotificationsPermission();
        return granted == true
            ? PermissionOutcome.granted
            : PermissionOutcome.denied;
      }

      final iosImpl = _plugin.resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin>();
      if (iosImpl != null) {
        final granted = await iosImpl.requestPermissions(
          alert: true,
          badge: true,
          sound: true,
        );
        return granted == true
            ? PermissionOutcome.granted
            : PermissionOutcome.denied;
      }

      // 対応するプラットフォーム実装が存在しない場合は拒否扱いとする。
      return PermissionOutcome.denied;
    } catch (e) {
      debugPrint('[NotificationService] 通知権限のリクエストに失敗: $e');
      return PermissionOutcome.requestError;
    }
  }

  /// 現在通知権限が付与されているかを返す（差し替え可能な内部フック）。
  ///
  /// iOS/Android の `flutter_local_notifications` の権限確認 API をラップする。
  /// - Android: [AndroidFlutterLocalNotificationsPlugin.areNotificationsEnabled]
  /// - iOS: [IOSFlutterLocalNotificationsPlugin.checkPermissions]
  ///
  /// 確認自体が失敗した場合や結果が不明な場合は false（未付与）として扱う。
  // ignore: unused_element
  Future<bool> _isPermissionGranted() async {
    try {
      final androidImpl = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      if (androidImpl != null) {
        final enabled = await androidImpl.areNotificationsEnabled();
        return enabled == true;
      }

      final iosImpl = _plugin.resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin>();
      if (iosImpl != null) {
        final options = await iosImpl.checkPermissions();
        return options?.isEnabled == true;
      }

      return false;
    } catch (e) {
      debugPrint('[NotificationService] 通知権限の確認に失敗: $e');
      return false;
    }
  }

  /// ScheduleWindow（本日から7日間）内の通知集合を計算する純粋関数。
  ///
  /// 副作用（`zonedSchedule` / SharedPreferences / OS 権限）を一切持たず、
  /// 与えられた入力のみから、スケジュールすべき [PlannedNotification] のリストを
  /// 決定的に計算する。これにより ScheduleWindow の計算ロジックを単体で検証できる。
  ///
  /// パラメータ:
  /// - [districtId]: 対象地区の District_ID（生成ペイロードには含めないが、
  ///   `entriesForDate` の呼び出しに用いる想定の識別子）。
  /// - [now]: 現在時刻。配信時刻がこれ以前（以下）の通知はスキップする（要件3.5）。
  /// - [eveningTime] / [morningTime]: EveningNotification / MorningNotification の時刻。
  /// - [eveningEnabledCategories] / [morningEnabledCategories]:
  ///   タイミング別に有効なカテゴリ集合。フィルタ後のカテゴリのみを対象とする。
  /// - [entriesForDate]: 対象日の収集エントリを返すコールバック
  ///   （通常 `ScheduleService.getScheduleForDate(districtId, date)`）。
  /// - [labelResolver]: カテゴリ → 日本語ラベル解決関数（既定は
  ///   [CategoryColors.getLabel]）。解決に失敗した場合、その日の当該タイミングの
  ///   通知はスキップする（要件3.4、try/catch で保護）。
  ///
  /// 挙動:
  /// - 本日 00:00 起点の7日間 `[today, today+6]` を対象とする（要件3.1, 3.2）。
  /// - カテゴリが空（またはフィルタ後に空）の日は通知を生成しない（要件3.6）。
  /// - EveningNotification は前日 + [eveningTime]。先頭日 `i == 0` は前日が
  ///   ScheduleWindow 範囲外のため対象外。
  /// - MorningNotification は当日 + [morningTime]。
  /// - 配信時刻が [now] 以前の通知はスケジュールしない（要件3.5）。
  /// - 本文にはフィルタ後カテゴリの日本語ラベルを `・` で連結して含める（要件3.3）。
  /// - ペイロードには対象収集日の ISO8601 文字列を格納する。
  static Future<List<PlannedNotification>> computeScheduleWindow({
    required String districtId,
    required DateTime now,
    required ({int hour, int minute}) eveningTime,
    required ({int hour, int minute}) morningTime,
    required List<GarbageCategory> eveningEnabledCategories,
    required List<GarbageCategory> morningEnabledCategories,
    required Future<List<ScheduleEntry>> Function(
            String districtId, DateTime date)
        entriesForDate,
    String Function(GarbageCategory category)? labelResolver,
  }) async {
    final resolveLabel = labelResolver ?? CategoryColors.getLabel;
    final today = DateTime(now.year, now.month, now.day);
    // 過去時刻スキップは注入クロック [now] のローカル表現を基準に判定する（要件3.5）。
    final nowTz = tz.TZDateTime(
      tz.local,
      now.year,
      now.month,
      now.day,
      now.hour,
      now.minute,
      now.second,
      now.millisecond,
      now.microsecond,
    );

    final planned = <PlannedNotification>[];

    for (int i = 0; i < 7; i++) {
      final targetDate = today.add(Duration(days: i));
      final entries = await entriesForDate(districtId, targetDate);

      // 収集予定が空の日は通知を生成しない（要件3.6）。
      if (entries.isEmpty) continue;

      final payload = DateTime(
        targetDate.year,
        targetDate.month,
        targetDate.day,
      ).toIso8601String();

      // --- EveningNotification（前日 + eveningTime） ---
      // 先頭日 i == 0 は前日が ScheduleWindow 範囲外のため対象外。
      if (i > 0) {
        final eveningEntries = entries
            .where((e) => eveningEnabledCategories.contains(e.category))
            .toList();

        if (eveningEntries.isNotEmpty) {
          final eveningBefore = tz.TZDateTime(
            tz.local,
            targetDate.year,
            targetDate.month,
            targetDate.day - 1,
            eveningTime.hour,
            eveningTime.minute,
          );

          // 配信時刻が現在時刻以前の通知はスキップする（要件3.5）。
          if (eveningBefore.isAfter(nowTz)) {
            // ラベル解決失敗時は当該タイミングの通知をスキップする（要件3.4）。
            try {
              final categoryNames =
                  eveningEntries.map((e) => resolveLabel(e.category)).join('・');
              planned.add(
                PlannedNotification(
                  title: '明日のゴミ出し',
                  body: '明日は$categoryNamesの日です',
                  scheduledDate: eveningBefore,
                  payload: payload,
                  isEvening: true,
                ),
              );
            } catch (e) {
              debugPrint('[NotificationService] evening ラベル解決に失敗、通知をスキップ: $e');
            }
          }
        }
      }

      // --- MorningNotification（当日 + morningTime） ---
      final morningEntries = entries
          .where((e) => morningEnabledCategories.contains(e.category))
          .toList();

      if (morningEntries.isNotEmpty) {
        final morningOf = tz.TZDateTime(
          tz.local,
          targetDate.year,
          targetDate.month,
          targetDate.day,
          morningTime.hour,
          morningTime.minute,
        );

        // 配信時刻が現在時刻以前の通知はスキップする（要件3.5）。
        if (morningOf.isAfter(nowTz)) {
          // ラベル解決失敗時は当該タイミングの通知をスキップする（要件3.4）。
          try {
            final categoryNames =
                morningEntries.map((e) => resolveLabel(e.category)).join('・');
            planned.add(
              PlannedNotification(
                title: '今日のゴミ出し',
                body: '今日は$categoryNamesの日です',
                scheduledDate: morningOf,
                payload: payload,
                isEvening: false,
              ),
            );
          } catch (e) {
            debugPrint('[NotificationService] morning ラベル解決に失敗、通知をスキップ: $e');
          }
        }
      }
    }

    return planned;
  }

  /// 今後7日分の通知をスケジュールする
  ///
  /// 各収集日について:
  /// - 前日のカスタム時刻: 「明日は○○ごみの日です」
  /// - 当日のカスタム時刻: 「今日は○○ごみの日です」
  ///
  /// ScheduleWindow の計算は純粋関数 [computeScheduleWindow] に委譲し、
  /// 本メソッドは `cancelAll` と `zonedSchedule` の副作用のみを担う。
  Future<void> scheduleWeeklyNotifications(String districtId) async {
    await initialize();
    await _plugin.cancelAll();

    final scheduleService = ScheduleService();

    // 保存済みの通知時刻を取得
    final eveningTime = await getEveningTime();
    final morningTime = await getMorningTime();

    // カテゴリフィルタリング用にカスタマイズサービスを取得
    final prefs = await SharedPreferences.getInstance();
    final customizationService = NotificationCustomizationService(prefs);
    final eveningEnabledCategories =
        await customizationService.getEnabledCategories(
      NotificationTimingType.evening,
    );
    final morningEnabledCategories =
        await customizationService.getEnabledCategories(
      NotificationTimingType.morning,
    );

    final planned = await computeScheduleWindow(
      districtId: districtId,
      now: _now(),
      eveningTime: eveningTime,
      morningTime: morningTime,
      eveningEnabledCategories: eveningEnabledCategories,
      morningEnabledCategories: morningEnabledCategories,
      entriesForDate: scheduleService.getScheduleForDate,
    );

    int notificationId = 0;
    for (final notification in planned) {
      await _scheduleNotification(
        id: notificationId++,
        title: notification.title,
        body: notification.body,
        scheduledDate: notification.scheduledDate,
        payload: notification.payload,
      );
    }

    debugPrint('[NotificationService] $notificationId件の通知をスケジュールしました');
  }

  /// 個別の通知をスケジュールする
  Future<void> _scheduleNotification({
    required int id,
    required String title,
    required String body,
    required tz.TZDateTime scheduledDate,
    String? payload,
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
      payload: payload,
    );
  }

  /// 通知のリスケジュール（地区変更時やアプリ起動時に呼ぶ）
  ///
  /// ReminderEnabledFlag が true のときのみ、現在の設定（保存済み District_ID・
  /// 通知時刻・現在時刻・収集スケジュール）から全通知を再計算する（要件 3.7, 4.5）。
  /// flag が false の場合は何もスケジュールしない（要件 1.5）。事前のスケジュール
  /// 状態には依存しないため、連続実行しても結果は同一（冪等）である。
  Future<void> refreshNotifications() async {
    final enabled = await isReminderEnabled();
    if (!enabled) return;

    final districtId = await _readDistrictId();
    if (districtId == null) return;

    await scheduleWeeklyNotifications(districtId);
  }

  /// 起動時に保存済みの通知設定を読み込み、必要に応じて再スケジュールする（要件 6.2〜6.5）。
  ///
  /// アプリ起動時に `main()` から呼び出す想定の復元処理。
  /// - SharedPreferences から ReminderEnabledFlag を読み込む（要件 6.2）。読み込みに
  ///   失敗した場合は [_readReminderEnabled] が既定値 false を返すため、flag=false
  ///   相当として動作し、何もスケジュールしない（要件 6.5）。
  /// - flag=true の場合、保存済みの District_ID に基づいて
  ///   [scheduleWeeklyNotifications] を実行し、ReminderNotification を再スケジュール
  ///   する（要件 6.3）。
  /// - 再スケジュール処理が失敗（例外）した場合でも、例外を捕捉して
  ///   ReminderEnabledFlag は true のまま保持する（要件 6.4）。次回起動・地区変更・
  ///   時刻変更で再試行できる。
  Future<void> restoreOnStartup() async {
    await initialize();

    // ReminderEnabledFlag を読み込む。読み込み失敗時は既定値 false（要件 6.2, 6.5）。
    final enabled = await isReminderEnabled();
    if (!enabled) {
      // flag=false 相当。新規通知はスケジュールしない（要件 6.5, 1.5）。
      return;
    }

    // 保存済みの District_ID を読み込む。読み込み失敗・未設定時は再スケジュールしない。
    final districtId = await _readDistrictId();
    if (districtId == null) {
      debugPrint('[NotificationService] 起動時: District_ID が未設定のため再スケジュールをスキップ');
      return;
    }

    // 再スケジュール失敗時も flag=true を保持する（要件 6.4）。
    try {
      await scheduleWeeklyNotifications(districtId);
      debugPrint('[NotificationService] 起動時の再スケジュールが完了しました');
    } catch (e) {
      // 例外を捕捉し flag は true のまま保持する。次回起動等で再試行可能（要件 6.4）。
      debugPrint('[NotificationService] 起動時の再スケジュールに失敗、flag=true を保持: $e');
    }
  }

  /// 選択中の District_ID を変更し、通知を再スケジュールする（要件 1.6, 3.7）。
  ///
  /// 地区切り替え時に呼び出す導線。新しい [districtId] を SharedPreferences へ
  /// 保存したうえで [refreshNotifications] を実行する。ReminderEnabledFlag が
  /// false の場合、保存は行うが通知はスケジュールされない（要件 1.5）。これにより、
  /// 再スケジュールは常に「現在の設定 + 現在時刻」から全通知を再計算する。
  Future<void> updateDistrict(String districtId) async {
    await _writeDistrictId(districtId);
    await refreshNotifications();
  }

  /// 前日通知の時刻を保存する（デフォルト: 20:00）
  ///
  /// 保存に成功した場合のみ通知を再スケジュールし、[SaveTimeResult.success]
  /// を返す（要件 4.2, 4.5）。保存に失敗した場合は変更前の値へロールバックし、
  /// [SaveTimeResult.failed] を返す（要件 4.4）。
  Future<SaveTimeResult> setEveningTime(int hour, int minute) async {
    // ロールバック用に変更前の値を保持する。
    final previous = await _readEveningTime();
    try {
      await _writeEveningTime(hour, minute);
    } catch (e) {
      debugPrint('[NotificationService] evening 時刻の保存に失敗: $e');
      // 変更前の値へロールバックする（要件 4.4）。
      // ロールバック自体の失敗は握りつぶし、failed を返す。
      try {
        await _writeEveningTime(previous.hour, previous.minute);
      } catch (rollbackError) {
        debugPrint(
            '[NotificationService] evening 時刻のロールバックに失敗: $rollbackError');
      }
      return SaveTimeResult.failed;
    }

    // 保存成功時のみ再スケジュールする（要件 4.5）。
    await refreshNotifications();
    return SaveTimeResult.success;
  }

  /// 当日通知の時刻を保存する（デフォルト: 06:00）
  ///
  /// 保存に成功した場合のみ通知を再スケジュールし、[SaveTimeResult.success]
  /// を返す（要件 4.3, 4.5）。保存に失敗した場合は変更前の値へロールバックし、
  /// [SaveTimeResult.failed] を返す（要件 4.4）。
  Future<SaveTimeResult> setMorningTime(int hour, int minute) async {
    // ロールバック用に変更前の値を保持する。
    final previous = await _readMorningTime();
    try {
      await _writeMorningTime(hour, minute);
    } catch (e) {
      debugPrint('[NotificationService] morning 時刻の保存に失敗: $e');
      // 変更前の値へロールバックする（要件 4.4）。
      // ロールバック自体の失敗は握りつぶし、failed を返す。
      try {
        await _writeMorningTime(previous.hour, previous.minute);
      } catch (rollbackError) {
        debugPrint(
            '[NotificationService] morning 時刻のロールバックに失敗: $rollbackError');
      }
      return SaveTimeResult.failed;
    }

    // 保存成功時のみ再スケジュールする（要件 4.5）。
    await refreshNotifications();
    return SaveTimeResult.success;
  }

  /// 前日通知の時刻を取得する（既定: 20:00）
  Future<({int hour, int minute})> getEveningTime() async {
    return _readEveningTime();
  }

  /// 当日通知の時刻を取得する（既定: 06:00）
  Future<({int hour, int minute})> getMorningTime() async {
    return _readMorningTime();
  }
}
