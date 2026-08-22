/// ゴミ品目のデータモデル
///
/// ゴミ分類カテゴリ（GarbageCategory）とゴミ品目（GarbageItem）を定義する。
/// JSONデータからの読み込みと書き出しに対応する。

import '../utils/localization_fallback_logger.dart';

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
/// 多言語対応のため、ローカライズされたフィールドとフォールバック付きの
/// displayゲッターを提供する。
class GarbageItem {
  final String id;
  final String name; // 日本語名（常に存在）
  final String? localizedName; // 選択言語での翻訳名
  final GarbageCategory primaryCategory;
  final List<GarbageCategory> secondaryCategories;
  final String disposalMethod; // 日本語出し方
  final String? localizedDisposalMethod; // 選択言語での翻訳
  final String? caution;
  final String? localizedCaution;
  final List<String> keywords; // 日本語キーワード
  final List<String> localizedKeywords; // 選択言語キーワード

  /// リクエストされた言語コード（フォールバックログに使用）
  final String? _requestedLanguage;

  /// 表示用名前（翻訳優先、フォールバックは日本語）
  ///
  /// ローカライズされた名前がない場合、デバッグビルドでフォールバックログを出力し、
  /// 日本語名を返す。nameは必須フィールドのため、nullや空文字にはならない。
  String get displayName {
    if (localizedName != null) return localizedName!;
    // フォールバック発生: デバッグモードでログ出力
    if (_requestedLanguage != null && _requestedLanguage != 'ja') {
      logFallbackUsage('name', id, _requestedLanguage!);
    }
    return name;
  }

  /// 表示用出し方（翻訳優先、フォールバックは日本語）
  ///
  /// ローカライズされた出し方がない場合、デバッグビルドでフォールバックログを出力し、
  /// 日本語の出し方を返す。
  String get displayDisposalMethod {
    if (localizedDisposalMethod != null) return localizedDisposalMethod!;
    // フォールバック発生: デバッグモードでログ出力
    if (_requestedLanguage != null && _requestedLanguage != 'ja') {
      logFallbackUsage('disposalMethod', id, _requestedLanguage!);
    }
    return disposalMethod;
  }

  /// 表示用注意事項（翻訳優先、フォールバックは日本語）
  ///
  /// ローカライズされた注意事項がない場合、日本語のcautionにフォールバックする。
  /// cautionはオプショナルフィールドのため、両方nullの場合はnullを返す（意図的）。
  String? get displayCaution {
    if (localizedCaution != null) return localizedCaution!;
    // フォールバック発生: デバッグモードでログ出力（ただしcaution自体がnullなら正常なのでログしない）
    if (caution != null &&
        _requestedLanguage != null &&
        _requestedLanguage != 'ja') {
      logFallbackUsage('caution', id, _requestedLanguage!);
    }
    return caution;
  }

  GarbageItem({
    required this.id,
    required this.name,
    this.localizedName,
    required this.primaryCategory,
    required this.secondaryCategories,
    required this.disposalMethod,
    this.localizedDisposalMethod,
    this.caution,
    this.localizedCaution,
    required this.keywords,
    this.localizedKeywords = const [],
    String? requestedLanguage,
  }) : _requestedLanguage = requestedLanguage;

  factory GarbageItem.fromJson(Map<String, dynamic> json,
      {String? requestedLanguage}) {
    return GarbageItem(
      id: json['id'] as String,
      name: json['name'] as String,
      localizedName:
          json['localized_name'] as String? ?? json['localizedName'] as String?,
      primaryCategory: GarbageCategoryExtension.fromString(
          json['primaryCategory'] as String),
      secondaryCategories: (json['secondaryCategories'] as List<dynamic>)
          .map((e) => GarbageCategoryExtension.fromString(e as String))
          .toList(),
      disposalMethod: json['disposalMethod'] as String? ??
          json['disposal_method'] as String? ??
          '',
      localizedDisposalMethod: json['localized_disposal_method'] as String? ??
          json['localizedDisposalMethod'] as String?,
      caution: json['caution'] as String?,
      localizedCaution: json['localized_caution'] as String? ??
          json['localizedCaution'] as String?,
      keywords: (json['keywords'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      localizedKeywords: (json['localized_keywords'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          (json['localizedKeywords'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      requestedLanguage: requestedLanguage,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'localizedName': localizedName,
      'primaryCategory': primaryCategory.toJsonString(),
      'secondaryCategories':
          secondaryCategories.map((e) => e.toJsonString()).toList(),
      'disposalMethod': disposalMethod,
      'localizedDisposalMethod': localizedDisposalMethod,
      'caution': caution,
      'localizedCaution': localizedCaution,
      'keywords': keywords,
      'localizedKeywords': localizedKeywords,
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
