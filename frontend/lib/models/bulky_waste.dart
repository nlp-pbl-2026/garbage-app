/// 粗大ごみ関連のデータモデル
///
/// 自治体設定（MunicipalityConfig）、申し込み手順（ApplicationStep）、
/// 粗大ごみ品目（BulkyWasteItem）、申し込み記録（ApplicationRecord）を定義する。
/// JSONデータからの読み込みと書き出しに対応する。

/// 手数料体系の種別
enum FeeStructureType {
  /// サイズ別手数料
  sizeBased,

  /// 重量別手数料
  weightBased,

  /// 一律手数料
  fixed,
}

/// FeeStructureTypeの文字列変換ヘルパー
extension FeeStructureTypeExtension on FeeStructureType {
  /// enum値をJSON文字列に変換
  String toJsonString() {
    switch (this) {
      case FeeStructureType.sizeBased:
        return 'size_based';
      case FeeStructureType.weightBased:
        return 'weight_based';
      case FeeStructureType.fixed:
        return 'fixed';
    }
  }

  /// JSON文字列からenum値に変換
  static FeeStructureType fromString(String value) {
    switch (value) {
      case 'size_based':
        return FeeStructureType.sizeBased;
      case 'weight_based':
        return FeeStructureType.weightBased;
      case 'fixed':
        return FeeStructureType.fixed;
      default:
        throw ArgumentError('Unknown FeeStructureType: $value');
    }
  }
}

/// 申し込み方法の種別
enum ApplicationMethod {
  /// Webフォーム
  webForm,

  /// 電話
  phone,

  /// Webフォームと電話の両方
  both,
}

/// ApplicationMethodの文字列変換ヘルパー
extension ApplicationMethodExtension on ApplicationMethod {
  /// enum値をJSON文字列に変換
  String toJsonString() {
    switch (this) {
      case ApplicationMethod.webForm:
        return 'web_form';
      case ApplicationMethod.phone:
        return 'phone';
      case ApplicationMethod.both:
        return 'both';
    }
  }

  /// JSON文字列からenum値に変換
  static ApplicationMethod fromString(String value) {
    switch (value) {
      case 'web_form':
        return ApplicationMethod.webForm;
      case 'phone':
        return ApplicationMethod.phone;
      case 'both':
        return ApplicationMethod.both;
      default:
        throw ArgumentError('Unknown ApplicationMethod: $value');
    }
  }
}

/// 申し込み状況
enum ApplicationStatus {
  /// 申し込み済み
  applied,

  /// 処理券購入済み
  ticketPurchased,

  /// 収集待ち
  awaitingCollection,

  /// 完了
  completed,
}

/// ApplicationStatusの文字列変換ヘルパー
extension ApplicationStatusExtension on ApplicationStatus {
  /// enum値をJSON文字列に変換
  String toJsonString() {
    switch (this) {
      case ApplicationStatus.applied:
        return 'applied';
      case ApplicationStatus.ticketPurchased:
        return 'ticket_purchased';
      case ApplicationStatus.awaitingCollection:
        return 'awaiting_collection';
      case ApplicationStatus.completed:
        return 'completed';
    }
  }

  /// JSON文字列からenum値に変換
  static ApplicationStatus fromString(String value) {
    switch (value) {
      case 'applied':
        return ApplicationStatus.applied;
      case 'ticket_purchased':
        return ApplicationStatus.ticketPurchased;
      case 'awaiting_collection':
        return ApplicationStatus.awaitingCollection;
      case 'completed':
        return ApplicationStatus.completed;
      default:
        throw ArgumentError('Unknown ApplicationStatus: $value');
    }
  }
}

/// 申し込み手順ステップ
///
/// 粗大ごみ申し込みの各手順を表す。
class ApplicationStep {
  final int stepNumber;
  final String title;
  final String description;
  final String? notes;

  ApplicationStep({
    required this.stepNumber,
    required this.title,
    required this.description,
    this.notes,
  });

  factory ApplicationStep.fromJson(Map<String, dynamic> json) {
    return ApplicationStep(
      stepNumber: json['step_number'] as int,
      title: json['title'] as String,
      description: json['description'] as String,
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'step_number': stepNumber,
      'title': title,
      'description': description,
      'notes': notes,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ApplicationStep &&
          runtimeType == other.runtimeType &&
          stepNumber == other.stepNumber &&
          title == other.title;

  @override
  int get hashCode => stepNumber.hashCode ^ title.hashCode;

  @override
  String toString() =>
      'ApplicationStep(stepNumber: $stepNumber, title: $title)';
}

/// 自治体粗大ごみ設定
///
/// 自治体ごとの粗大ごみ収集に関する設定情報を保持する。
class MunicipalityConfig {
  final String municipalityId;
  final String municipalityName;
  final String collectionFrequency;
  final String receptionHours;
  final String collectionRules;
  final FeeStructureType feeStructureType;
  final ApplicationMethod applicationMethod;
  final String? webFormUrl;
  final String? phoneNumber;
  final List<ApplicationStep> steps;

  MunicipalityConfig({
    required this.municipalityId,
    required this.municipalityName,
    required this.collectionFrequency,
    required this.receptionHours,
    required this.collectionRules,
    required this.feeStructureType,
    required this.applicationMethod,
    this.webFormUrl,
    this.phoneNumber,
    required this.steps,
  });

  factory MunicipalityConfig.fromJson(Map<String, dynamic> json) {
    return MunicipalityConfig(
      municipalityId: json['municipality_id'] as String,
      municipalityName: json['municipality_name'] as String,
      collectionFrequency: json['collection_frequency'] as String,
      receptionHours: json['reception_hours'] as String,
      collectionRules: json['collection_rules'] as String,
      feeStructureType: FeeStructureTypeExtension.fromString(
          json['fee_structure_type'] as String),
      applicationMethod: ApplicationMethodExtension.fromString(
          json['application_method'] as String),
      webFormUrl: json['web_form_url'] as String?,
      phoneNumber: json['phone_number'] as String?,
      steps: (json['steps'] as List<dynamic>)
          .map((e) => ApplicationStep.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'municipality_id': municipalityId,
      'municipality_name': municipalityName,
      'collection_frequency': collectionFrequency,
      'reception_hours': receptionHours,
      'collection_rules': collectionRules,
      'fee_structure_type': feeStructureType.toJsonString(),
      'application_method': applicationMethod.toJsonString(),
      'web_form_url': webFormUrl,
      'phone_number': phoneNumber,
      'steps': steps.map((e) => e.toJson()).toList(),
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is MunicipalityConfig &&
          runtimeType == other.runtimeType &&
          municipalityId == other.municipalityId;

  @override
  int get hashCode => municipalityId.hashCode;

  @override
  String toString() =>
      'MunicipalityConfig(municipalityId: $municipalityId, municipalityName: $municipalityName)';
}

/// 粗大ごみ品目
///
/// 品目名、カテゴリ、手数料、サイズ/重量情報を保持する。
class BulkyWasteItem {
  final int id;
  final String itemName;
  final String category;
  final int feeAmount;
  final String? sizeCategory;
  final int? sizeThresholdCm;
  final String? weightCategory;
  final double? weightThresholdKg;
  final String? notes;

  /// GarbageItemとのマッピング用品目名（完全一致で照合）
  final String? garbageItemName;

  BulkyWasteItem({
    required this.id,
    required this.itemName,
    required this.category,
    required this.feeAmount,
    this.sizeCategory,
    this.sizeThresholdCm,
    this.weightCategory,
    this.weightThresholdKg,
    this.notes,
    this.garbageItemName,
  });

  factory BulkyWasteItem.fromJson(Map<String, dynamic> json) {
    return BulkyWasteItem(
      id: json['id'] as int,
      itemName: json['item_name'] as String,
      category: json['category'] as String,
      feeAmount: json['fee_amount'] as int,
      sizeCategory: json['size_category'] as String?,
      sizeThresholdCm: json['size_threshold_cm'] as int?,
      weightCategory: json['weight_category'] as String?,
      weightThresholdKg: (json['weight_threshold_kg'] as num?)?.toDouble(),
      notes: json['notes'] as String?,
      garbageItemName: json['garbage_item_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'item_name': itemName,
      'category': category,
      'fee_amount': feeAmount,
      'size_category': sizeCategory,
      'size_threshold_cm': sizeThresholdCm,
      'weight_category': weightCategory,
      'weight_threshold_kg': weightThresholdKg,
      'notes': notes,
      'garbage_item_name': garbageItemName,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BulkyWasteItem &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          itemName == other.itemName;

  @override
  int get hashCode => id.hashCode ^ itemName.hashCode;

  @override
  String toString() =>
      'BulkyWasteItem(id: $id, itemName: $itemName, feeAmount: $feeAmount)';
}

/// 申し込み状況記録（ローカル保存）
///
/// 粗大ごみ申し込みの進捗状況を端末内に記録する。
class ApplicationRecord {
  final String id;
  final String itemName;
  final DateTime collectionDate;
  final ApplicationStatus status;
  final DateTime createdAt;
  final DateTime updatedAt;

  /// itemNameの最大文字数
  static const int maxItemNameLength = 50;

  ApplicationRecord({
    required this.id,
    required this.itemName,
    required this.collectionDate,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  }) : assert(itemName.length <= maxItemNameLength,
            'itemName must be at most $maxItemNameLength characters');

  factory ApplicationRecord.fromJson(Map<String, dynamic> json) {
    return ApplicationRecord(
      id: json['id'] as String,
      itemName: json['item_name'] as String,
      collectionDate: DateTime.parse(json['collection_date'] as String),
      status: ApplicationStatusExtension.fromString(json['status'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'item_name': itemName,
      'collection_date': collectionDate.toIso8601String(),
      'status': status.toJsonString(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  /// ステータスを更新した新しいレコードを返す
  ApplicationRecord copyWithStatus(ApplicationStatus newStatus) {
    return ApplicationRecord(
      id: id,
      itemName: itemName,
      collectionDate: collectionDate,
      status: newStatus,
      createdAt: createdAt,
      updatedAt: DateTime.now(),
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ApplicationRecord &&
          runtimeType == other.runtimeType &&
          id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() =>
      'ApplicationRecord(id: $id, itemName: $itemName, status: $status)';
}
