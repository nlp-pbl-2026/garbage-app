import 'package:flutter/material.dart';
import '../constants/colors.dart';
import 'garbage_item.dart';

/// カテゴリ色・ラベルマッピング
///
/// 地域定義を優先し、松山市の旧カテゴリには互換の色・ラベルを提供する。
/// すべての画面で同一のカテゴリに同一の色とラベルを使用し、一貫性を保つ。
class CategoryColors {
  // プライベートコンストラクタ（インスタンス化防止）
  CategoryColors._();
  static const List<GarbageCategory> collectionCategories = [
    GarbageCategory.burnable, GarbageCategory.paper, GarbageCategory.metalGlass,
    GarbageCategory.landfill, GarbageCategory.mercury, GarbageCategory.plastic,
    GarbageCategory.petBottle, GarbageCategory.cans, GarbageCategory.bottles,
    GarbageCategory.bulky,
  ];

  /// カテゴリ → 色のマッピング
  static final Map<GarbageCategory, Color> colorMap = Map.unmodifiable({
    GarbageCategory.burnable: AppColors.burnable,
    GarbageCategory.recyclable: AppColors.recyclable,
    GarbageCategory.plastic: AppColors.plastic,
    GarbageCategory.petBottle: AppColors.petBottle,
    GarbageCategory.hazardous: AppColors.hazardous,
    GarbageCategory.paper: AppColors.recyclable,
    GarbageCategory.metalGlass: AppColors.recyclable,
    GarbageCategory.landfill: AppColors.hazardous,
    GarbageCategory.mercury: AppColors.hazardous,
    GarbageCategory.cans: AppColors.recyclable,
    GarbageCategory.bottles: AppColors.recyclable,
    GarbageCategory.bulky: AppColors.hazardous,
  });

  /// カテゴリ → ラベル（日本語名）のマッピング
  static final Map<GarbageCategory, String> labelMap = Map.unmodifiable({
    GarbageCategory.burnable: '可燃ごみ',
    GarbageCategory.recyclable: '資源ごみ',
    GarbageCategory.plastic: 'プラスチック製容器包装',
    GarbageCategory.petBottle: 'ペットボトル',
    GarbageCategory.hazardous: '危険ごみ',
    GarbageCategory.paper: '紙類',
    GarbageCategory.metalGlass: '金物・ガラス類',
    GarbageCategory.landfill: '埋立ごみ',
    GarbageCategory.mercury: '水銀ごみ',
    GarbageCategory.cans: '缶類',
    GarbageCategory.bottles: 'びん類',
    GarbageCategory.bulky: '粗大ごみ',
  });

  /// 指定カテゴリの色を取得
  static Color getColor(GarbageCategory category) {
    return category.colorValue == null
        ? colorMap[category] ?? Colors.blueGrey
        : Color(category.colorValue!);
  }

  /// 指定カテゴリのラベルを取得
  static String getLabel(GarbageCategory category) {
    return category.displayName ?? labelMap[category] ?? category.id;
  }
}
