/// ゴミ品目のデータモデル
///
/// ゴミ分類カテゴリ（GarbageCategory）とゴミ品目（GarbageItem）を定義する。
/// JSONデータからの読み込みと書き出しに対応する。

/// ゴミ分類カテゴリ
///
/// 各カテゴリは固定の色とラベルが割り当てられる。
enum GarbageCategory {
  /// 可燃ごみ - ピンク
  burnable,

  /// 資源ごみ - 緑
  recyclable,

  /// プラスチック製容器包装 - オレンジ
  plastic,

  /// ペットボトル - 青
  petBottle,

  /// 危険ごみ - 赤
  hazardous,
}

/// GarbageCategoryの文字列変換ヘルパー
extension GarbageCategoryExtension on GarbageCategory {
  /// enum値をJSON文字列に変換
  String toJsonString() {
    switch (this) {
      case GarbageCategory.burnable:
        return 'burnable';
      case GarbageCategory.recyclable:
        return 'recyclable';
      case GarbageCategory.plastic:
        return 'plastic';
      case GarbageCategory.petBottle:
        return 'petBottle';
      case GarbageCategory.hazardous:
        return 'hazardous';
    }
  }

  /// JSON文字列からenum値に変換
  static GarbageCategory fromString(String value) {
    switch (value) {
      case 'burnable':
        return GarbageCategory.burnable;
      case 'recyclable':
        return GarbageCategory.recyclable;
      case 'plastic':
        return GarbageCategory.plastic;
      case 'petBottle':
        return GarbageCategory.petBottle;
      case 'hazardous':
        return GarbageCategory.hazardous;
      default:
        throw ArgumentError('Unknown GarbageCategory: $value');
    }
  }
}

/// ゴミ品目
///
/// 品目名、分類、出し方、注意事項、検索キーワードを保持する。
class GarbageItem {
  final String id;
  final String name;
  final GarbageCategory primaryCategory;
  final List<GarbageCategory> secondaryCategories;
  final String disposalMethod;
  final String? caution;
  final List<String> keywords;

  GarbageItem({
    required this.id,
    required this.name,
    required this.primaryCategory,
    required this.secondaryCategories,
    required this.disposalMethod,
    this.caution,
    required this.keywords,
  });

  factory GarbageItem.fromJson(Map<String, dynamic> json) {
    return GarbageItem(
      id: json['id'] as String,
      name: json['name'] as String,
      primaryCategory:
          GarbageCategoryExtension.fromString(json['primaryCategory'] as String),
      secondaryCategories: (json['secondaryCategories'] as List<dynamic>)
          .map((e) => GarbageCategoryExtension.fromString(e as String))
          .toList(),
      disposalMethod: json['disposalMethod'] as String,
      caution: json['caution'] as String?,
      keywords: (json['keywords'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'primaryCategory': primaryCategory.toJsonString(),
      'secondaryCategories':
          secondaryCategories.map((e) => e.toJsonString()).toList(),
      'disposalMethod': disposalMethod,
      'caution': caution,
      'keywords': keywords,
    };
  }

  /// 複数カテゴリに該当するか
  ///
  /// secondaryCategoriesが非空の場合にtrueを返す。
  bool get hasMultipleCategories => secondaryCategories.isNotEmpty;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GarbageItem &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          name == other.name &&
          primaryCategory == other.primaryCategory;

  @override
  int get hashCode => id.hashCode ^ name.hashCode ^ primaryCategory.hashCode;

  @override
  String toString() =>
      'GarbageItem(id: $id, name: $name, primaryCategory: $primaryCategory)';
}
