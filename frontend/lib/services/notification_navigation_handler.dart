/// 通知タップ時のナビゲーションハンドラ
///
/// ローカル通知タップ時のペイロード（対象収集日の ISO8601 文字列）を解釈し、
/// カレンダー（収集日詳細）画面へ遷移する（要件 5.1, 5.2）。
///
/// 本ハンドラは `MaterialApp.navigatorKey` に接続する [GlobalKey]<[NavigatorState]>
/// を保持する。実際に「カレンダーの該当日を選択状態で開く」動作はアプリ側の状態管理
/// （Riverpod の `selectedDayProvider` / `focusedMonthProvider` と MainScreen のタブ切替）
/// に依存するため、遷移意図を受け取るコールバック [onNavigateToCollectionDay] へ委譲する。
/// これにより本ハンドラはプラグイン・UI 双方から分離され、単体で検証可能になる。
///
/// 配線（task 9.3）の想定:
/// - [navigatorKey] を `MaterialApp(navigatorKey: handler.navigatorKey, ...)` に渡す。
/// - [notificationResponseCallback] を `NotificationService.initialize` の
///   `onDidReceiveNotificationResponse` に接続する。
/// - [onNavigateToCollectionDay] で `selectedDayProvider` / `focusedMonthProvider` を更新し、
///   MainScreen のカレンダータブへ切り替える。
/// - UI 準備完了後（最初のフレーム後）に [handleAppLaunchDetails] を呼ぶ。
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// 対象収集日を伴う「カレンダーへ遷移」意図を受け取るコールバック。
///
/// [targetDate] はペイロードから復元した収集日（00:00 に正規化済み）。
/// ペイロードが空・解釈不能な場合は null を渡す（この場合はカレンダーを
/// 特定日選択なしで開く想定）。
typedef NavigateToCollectionDay = void Function(DateTime? targetDate);

/// 通知タップ時のペイロード解釈と画面遷移を担うハンドラ。
class NotificationNavigationHandler {
  /// `MaterialApp.navigatorKey` に接続する Navigator キー。
  ///
  /// コールドスタート時の遷移や、コンテキスト非依存のナビゲーションに使用する。
  /// 省略時は新規に生成する。
  final GlobalKey<NavigatorState> navigatorKey;

  /// 対象収集日を伴うカレンダー遷移意図の受け口。
  ///
  /// 「カレンダーの該当日を選択状態で開く」具体的な処理（Riverpod の状態更新・
  /// MainScreen のタブ切替）はアプリ側に依存するため、配線時（task 9.3）に注入する。
  final NavigateToCollectionDay onNavigateToCollectionDay;

  /// 通知プラグイン。コールドスタート起動要因の確認に用いる。
  ///
  /// 省略時は `FlutterLocalNotificationsPlugin` の新規インスタンスを使用する。
  /// テスト時はフェイクを注入できる。
  final FlutterLocalNotificationsPlugin _plugin;

  NotificationNavigationHandler({
    required this.onNavigateToCollectionDay,
    GlobalKey<NavigatorState>? navigatorKey,
    FlutterLocalNotificationsPlugin? plugin,
  })  : navigatorKey = navigatorKey ?? GlobalKey<NavigatorState>(),
        _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  /// フォアグラウンド/バックグラウンドからの通知タップ応答を処理する（要件 5.1）。
  ///
  /// `NotificationService.initialize` の `onDidReceiveNotificationResponse`
  /// コールバックへ接続する想定。ペイロード（ISO8601 収集日）を解釈し
  /// [navigateToCollectionDay] を呼ぶ。
  void onNotificationResponse(NotificationResponse response) {
    final targetDate = _parsePayload(response.payload);
    navigateToCollectionDay(targetDate);
  }

  /// `NotificationService.initialize` に渡すためのコールバック。
  ///
  /// task 9.3 でこの getter を
  /// `NotificationService.initialize(onDidReceiveNotificationResponse: handler.notificationResponseCallback)`
  /// のように接続する（NotificationService 側の initialize がこの引数を受けるよう拡張される）。
  DidReceiveNotificationResponseCallback get notificationResponseCallback =>
      onNotificationResponse;

  /// コールドスタート時の起動要因を確認し、通知起動なら遷移する（要件 5.2）。
  ///
  /// アプリが通知タップによって起動された場合、`getNotificationAppLaunchDetails()`
  /// の `didNotificationLaunchApp` が true になる。この場合、UI（Navigator）が
  /// 準備できてから遷移する必要があるため、最初のフレーム描画後
  /// （[WidgetsBinding.addPostFrameCallback]）に遷移を実行する。
  ///
  /// UI 準備完了後（例: MaterialApp 構築後）に呼び出すことを想定する。
  Future<void> handleAppLaunchDetails() async {
    NotificationAppLaunchDetails? details;
    try {
      details = await _plugin.getNotificationAppLaunchDetails();
    } catch (e) {
      debugPrint('[NotificationNavigationHandler] 起動要因の取得に失敗: $e');
      return;
    }

    if (details == null || !details.didNotificationLaunchApp) {
      // 通知以外の要因で起動された場合は何もしない。
      return;
    }

    final targetDate = _parsePayload(details.notificationResponse?.payload);

    // コールドスタートでは UI がまだ準備できていない可能性があるため、
    // 最初のフレーム後に遷移する（要件 5.2）。
    WidgetsBinding.instance.addPostFrameCallback((_) {
      navigateToCollectionDay(targetDate);
    });
  }

  /// カレンダー（収集日詳細）画面を、指定日を選択状態で開く（要件 5.1）。
  ///
  /// 具体的な「該当日を選択状態で開く」処理は [onNavigateToCollectionDay] へ委譲する。
  /// [targetDate] は時刻成分を切り捨てた日付（00:00）に正規化して渡す。
  void navigateToCollectionDay(DateTime? targetDate) {
    final normalized = targetDate == null
        ? null
        : DateTime(targetDate.year, targetDate.month, targetDate.day);
    onNavigateToCollectionDay(normalized);
  }

  /// ペイロード（ISO8601 収集日文字列）を [DateTime] に解釈する。
  ///
  /// null・空文字・解釈不能な文字列の場合は null を返す（安全側）。
  DateTime? _parsePayload(String? payload) {
    if (payload == null || payload.isEmpty) {
      return null;
    }
    final parsed = DateTime.tryParse(payload);
    if (parsed == null) {
      debugPrint('[NotificationNavigationHandler] ペイロードの解釈に失敗: $payload');
      return null;
    }
    return DateTime(parsed.year, parsed.month, parsed.day);
  }
}
