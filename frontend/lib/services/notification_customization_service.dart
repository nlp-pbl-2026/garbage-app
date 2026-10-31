import 'package:shared_preferences/shared_preferences.dart';

import '../models/garbage_item.dart';
import '../models/garbage_category.dart';
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
  /// 松山市は旧キー、その他は自治体ID・分別設定IDを含むキーを使う。
  /// 例: `notification_category_burnable_evening`
  String _buildKey(GarbageCategory category, NotificationTimingType timing) {
    final scope = category.scope == null ? '' : '${category.scope}/';
    return '$_keyPrefix$scope${category.toJsonString()}_${timing.name}';
  }

  /// 全カテゴリの通知設定を読み込む
  ///
  /// SharedPreferencesにキーが存在しない場合はデフォルトtrue（ON）を返す。
  /// 対象地域の収集区分ごとに前日・当日の設定を読み込む。
  Future<Map<GarbageCategory, CategoryNotificationSetting>> loadAllSettings(
      {List<GarbageCategory> categories =
          CategoryColors.collectionCategories}) async {
    final Map<GarbageCategory, CategoryNotificationSetting> settings = {};

    for (final category in categories) {
      final eveningKey = _buildKey(category, NotificationTimingType.evening);
      final morningKey = _buildKey(category, NotificationTimingType.morning);

      final legacy = _legacyCategory(category);
      final eveningEnabled = _prefs.getBool(eveningKey) ??
          (legacy == null ? null : _prefs.getBool(_buildKey(legacy, NotificationTimingType.evening))) ?? true;
      final morningEnabled = _prefs.getBool(morningKey) ??
          (legacy == null ? null : _prefs.getBool(_buildKey(legacy, NotificationTimingType.morning))) ?? true;

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
    NotificationTimingType timing, {
    List<GarbageCategory> categories = CategoryColors.collectionCategories,
  }) async {
    final List<GarbageCategory> enabledCategories = [];

    for (final category in categories) {
      final key = _buildKey(category, timing);
      final legacy = _legacyCategory(category);
      final enabled = _prefs.getBool(key) ??
          (legacy == null ? null : _prefs.getBool(_buildKey(legacy, timing))) ?? true;
      if (enabled) {
        enabledCategories.add(category);
      }
    }

    return enabledCategories;
  }

  GarbageCategory? _legacyCategory(GarbageCategory category) {
    if (category.scope != null) return null;
    switch (category) {
      case GarbageCategory.paper:
      case GarbageCategory.metalGlass:
      case GarbageCategory.cans:
      case GarbageCategory.bottles:
        return GarbageCategory.recyclable;
      case GarbageCategory.landfill:
      case GarbageCategory.mercury:
      case GarbageCategory.bulky:
        return GarbageCategory.hazardous;
      default:
        return null;
    }
  }
}
