/// ゴミ品目のデータモデル
///
/// ゴミ分類カテゴリ（GarbageCategory）とゴミ品目（GarbageItem）を定義する。
/// JSONデータからの読み込みと書き出しに対応する。

/// A collection stream. Legacy constants retain Matsuyama's saved preference keys.
/// Other municipalities use scoped values; identical stream IDs never imply identical rules.
class GarbageCategory {
  final String id;
  final String? scope;
  final String? displayName;
  final int? colorValue;
  final String cutoff;
  const GarbageCategory._(this.id, {this.cutoff = '08:00'})
      : scope = null,
        displayName = null,
        colorValue = null;
  const GarbageCategory.regional(
      {required this.id,
      required this.scope,
      required this.displayName,
      required this.cutoff,
      this.colorValue});

  static const burnable = GarbageCategory._('burnable', cutoff: '07:00');
  static const recyclable = GarbageCategory._('recyclable');
  static const plastic = GarbageCategory._('plastic');
  static const petBottle = GarbageCategory._('petBottle');
  static const hazardous = GarbageCategory._('hazardous');
  static const paper = GarbageCategory._('paper');
  static const metalGlass = GarbageCategory._('metal_glass');
  static const landfill = GarbageCategory._('landfill');
  static const mercury = GarbageCategory._('mercury');
  static const cans = GarbageCategory._('cans');
  static const bottles = GarbageCategory._('bottles');
  static const bulky = GarbageCategory._('bulky');
  static const values = [
    burnable,
    recyclable,
    plastic,
    petBottle,
    hazardous,
    paper,
    metalGlass,
    landfill,
    mercury,
    cans,
    bottles,
    bulky
  ];

  int get cutoffMinutes {
    final parts = cutoff.split(':');
    return int.parse(parts[0]) * 60 + int.parse(parts[1]);
  }

  String get deadlineLabel {
    final parts = cutoff.split(':');
    return '${int.parse(parts[0])}時${parts[1] == '00' ? '' : '${int.parse(parts[1])}分'}';
  }

  @override
  bool operator ==(Object other) =>
      other is GarbageCategory && id == other.id && scope == other.scope;
  @override
  int get hashCode => Object.hash(id, scope);
}

/// GarbageCategoryの文字列変換ヘルパー
extension GarbageCategoryExtension on GarbageCategory {
  /// 保存用のカテゴリID文字列に変換
  String toJsonString() {
    return id;
  }

  /// 松山市の保存済みIDと収集区分IDを互換読み込みする
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
      case 'combustible':
        return GarbageCategory.burnable;
      case 'plastic_packaging':
        return GarbageCategory.plastic;
      case 'pet_bottle':
        return GarbageCategory.petBottle;
      case 'paper':
        return GarbageCategory.paper;
      case 'metal_glass':
        return GarbageCategory.metalGlass;
      case 'landfill':
        return GarbageCategory.landfill;
      case 'mercury':
        return GarbageCategory.mercury;
      case 'cans':
        return GarbageCategory.cans;
      case 'bottles':
        return GarbageCategory.bottles;
      case 'bulky':
        return GarbageCategory.bulky;
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
