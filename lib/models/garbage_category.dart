import 'package:flutter/material.dart';
import '../constants/colors.dart';
import 'garbage_item.dart';

/// カテゴリ色・ラベルマッピング
///
/// GarbageCategoryに対する固定の色とテキストラベルを提供する。
/// すべての画面で同一のカテゴリに同一の色とラベルを使用し、一貫性を保つ。
class CategoryColors {
  // プライベートコンストラクタ（インスタンス化防止）
  CategoryColors._();

  /// カテゴリ → 色のマッピング
  static const Map<GarbageCategory, Color> colorMap = {
    GarbageCategory.burnable: AppColors.burnable,
    GarbageCategory.recyclable: AppColors.recyclable,
    GarbageCategory.plastic: AppColors.plastic,
    GarbageCategory.petBottle: AppColors.petBottle,
    GarbageCategory.hazardous: AppColors.hazardous,
  };

  /// カテゴリ → ラベル（日本語名）のマッピング
  static const Map<GarbageCategory, String> labelMap = {
    GarbageCategory.burnable: '可燃ごみ',
    GarbageCategory.recyclable: '資源ごみ',
    GarbageCategory.plastic: 'プラスチック製容器包装',
    GarbageCategory.petBottle: 'ペットボトル',
    GarbageCategory.hazardous: '危険ごみ',
  };

  /// 指定カテゴリの色を取得
  static Color getColor(GarbageCategory category) {
    return colorMap[category]!;
  }

  /// 指定カテゴリのラベルを取得
  static String getLabel(GarbageCategory category) {
    return labelMap[category]!;
  }
}
