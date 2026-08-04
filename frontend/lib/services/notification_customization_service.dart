import 'package:shared_preferences/shared_preferences.dart';

import '../models/garbage_item.dart';
import '../models/category_notification_setting.dart';
import '../models/notification_timing_type.dart';

/// ゴミ種別ごとの通知ON/OFF設定を管理するサービス
///
/// SharedPreferencesを使用して、各GarbageCategoryの前日通知・当日通知の
/// 有効/無効設定を永続化する。キーが存在しない場合はデフォルトtrue（ON）を返す。
class NotificationCustomizationService {
  /// SharedPreferencesキーのプレフィックス
  static const String _keyPrefix = 'notification_category_';

  final SharedPreferences _prefs;

  NotificationCustomizationService(this._prefs);

  /// 指定カテゴリ・タイミングの設定キーを生成する
  ///
  /// 形式: `notification_category_{category}_{timing}`
  /// 例: `notification_category_burnable_evening`
  String _buildKey(GarbageCategory category, NotificationTimingType timing) {
    return '${_keyPrefix}${category.toJsonString()}_${timing.name}';
  }

  /// 全カテゴリの通知設定を読み込む
  ///
  /// SharedPreferencesにキーが存在しない場合はデフォルトtrue（ON）を返す。
  /// 5カテゴリ × 2タイミング = 10個の設定値を読み込む。
  Future<Map<GarbageCategory, CategoryNotificationSetting>> loadAllSettings() async {
    final Map<GarbageCategory, CategoryNotificationSetting> settings = {};

    for (final category in GarbageCategory.values) {
      final eveningKey = _buildKey(category, NotificationTimingType.evening);
      final morningKey = _buildKey(category, NotificationTimingType.morning);

      final eveningEnabled = _prefs.getBool(eveningKey) ?? true;
      final morningEnabled = _prefs.getBool(morningKey) ?? true;

      settings[category] = CategoryNotificationSetting(
        category: category,
        eveningEnabled: eveningEnabled,
        morningEnabled: morningEnabled,
      );
    }

    return settings;
  }

  /// 指定カテゴリ・タイミングの通知設定を保存する
  ///
  /// 変更を即座にSharedPreferencesへ保存する。
  Future<void> saveSetting(
    GarbageCategory category,
    NotificationTimingType timing,
    bool enabled,
  ) async {
    final key = _buildKey(category, timing);
    await _prefs.setBool(key, enabled);
  }

  /// 指定タイミングで通知が有効なカテゴリ一覧を返す
  ///
  /// 該当タイミングでONに設定されているカテゴリのみを返す。
  /// キーが存在しない場合はデフォルトtrue（ON）として扱う。
  Future<List<GarbageCategory>> getEnabledCategories(
    NotificationTimingType timing,
  ) async {
    final List<GarbageCategory> enabledCategories = [];

    for (final category in GarbageCategory.values) {
      final key = _buildKey(category, timing);
      final enabled = _prefs.getBool(key) ?? true;
      if (enabled) {
        enabledCategories.add(category);
      }
    }

    return enabledCategories;
  }
}
