import 'package:garbage_app/models/garbage_item.dart';

/// 各ゴミ種別に対する通知タイミング別ON/OFF設定
///
/// GarbageCategoryごとに前日通知（evening）と当日通知（morning）の
/// 有効/無効を保持するイミュータブルモデル。
class CategoryNotificationSetting {
  final GarbageCategory category;
  final bool eveningEnabled;
  final bool morningEnabled;

  const CategoryNotificationSetting({
    required this.category,
    this.eveningEnabled = true,
    this.morningEnabled = true,
  });

  CategoryNotificationSetting copyWith({
    bool? eveningEnabled,
    bool? morningEnabled,
  }) {
    return CategoryNotificationSetting(
      category: category,
      eveningEnabled: eveningEnabled ?? this.eveningEnabled,
      morningEnabled: morningEnabled ?? this.morningEnabled,
    );
  }
}
