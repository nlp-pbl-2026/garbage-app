/// 通知サービス（モック実装）
///
/// リマインダー通知の有効化/無効化をSharedPreferencesで管理する。
/// プロトタイプ段階のため、実際のプッシュ通知配信は行わず、
/// debugPrintによるログ出力のみ実施する。

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// リマインダー通知設定のキー
const String _reminderEnabledKey = 'reminder_enabled';

/// 通知サービス
///
/// 収集日前日リマインダーの有効/無効を管理する。
/// プロトタイプ段階では実際の通知配信は行わず、ログ出力で代替する。
class NotificationService {
  /// リマインダー通知を有効化する
  ///
  /// SharedPreferencesに有効フラグを保存し、ログを出力する。
  /// 本番実装では、ここでプッシュ通知のスケジューリングを行う。
  Future<void> enableReminder() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reminderEnabledKey, true);
    debugPrint('[NotificationService] リマインダー通知を有効化しました');
  }

  /// リマインダー通知を無効化する
  ///
  /// SharedPreferencesの有効フラグをfalseに設定し、ログを出力する。
  /// 本番実装では、ここでスケジュール済み通知のキャンセルを行う。
  Future<void> disableReminder() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reminderEnabledKey, false);
    debugPrint('[NotificationService] リマインダー通知を無効化しました');
  }

  /// リマインダー通知の有効状態を取得する
  ///
  /// SharedPreferencesから値を読み込む。
  /// 未設定の場合はデフォルトでfalse（無効）を返す。
  Future<bool> isReminderEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_reminderEnabledKey) ?? false;
  }
}
