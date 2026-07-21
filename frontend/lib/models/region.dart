/// 地域関連のデータモデル
///
/// 都道府県、市区町村、地区の3階層構造で地域データを管理する。
/// RegionSettingは選択された地域設定を保持し、SharedPreferencesに保存される。

/// 都道府県
class Prefecture {
  final String id;
  final String name;

  Prefecture({required this.id, required this.name});

  factory Prefecture.fromJson(Map<String, dynamic> json) {
    return Prefecture(
      id: json['id'] as String,
      name: json['name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Prefecture &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          name == other.name;

  @override
  int get hashCode => id.hashCode ^ name.hashCode;

  @override
  String toString() => 'Prefecture(id: $id, name: $name)';
}

/// 市区町村
class Municipality {
  final String id;
  final String prefectureId;
  final String name;

  Municipality({
    required this.id,
    required this.prefectureId,
    required this.name,
  });

  factory Municipality.fromJson(Map<String, dynamic> json) {
    return Municipality(
      id: json['id'] as String,
      prefectureId: json['prefectureId'] as String,
      name: json['name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'prefectureId': prefectureId,
      'name': name,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Municipality &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          prefectureId == other.prefectureId &&
          name == other.name;

  @override
  int get hashCode => id.hashCode ^ prefectureId.hashCode ^ name.hashCode;

  @override
  String toString() =>
      'Municipality(id: $id, prefectureId: $prefectureId, name: $name)';
}

/// 地区
class District {
  final String id;
  final String municipalityId;
  final String name;

  District({
    required this.id,
    required this.municipalityId,
    required this.name,
  });

  factory District.fromJson(Map<String, dynamic> json) {
    return District(
      id: json['id'] as String,
      municipalityId: json['municipalityId'] as String,
      name: json['name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'municipalityId': municipalityId,
      'name': name,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is District &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          municipalityId == other.municipalityId &&
          name == other.name;

  @override
  int get hashCode =>
      id.hashCode ^ municipalityId.hashCode ^ name.hashCode;

  @override
  String toString() =>
      'District(id: $id, municipalityId: $municipalityId, name: $name)';
}

/// 地域設定（保存用）
///
/// ユーザーが選択した地域情報を保持する。
/// SharedPreferencesに保存し、アプリ起動時に読み込む。
class RegionSetting {
  final String prefectureId;
  final String prefectureName;
  final String municipalityId;
  final String municipalityName;
  final String districtId;
  final String districtName;

  RegionSetting({
    required this.prefectureId,
    required this.prefectureName,
    required this.municipalityId,
    required this.municipalityName,
    required this.districtId,
    required this.districtName,
  });

  factory RegionSetting.fromJson(Map<String, dynamic> json) {
    return RegionSetting(
      prefectureId: json['prefectureId'] as String,
      prefectureName: json['prefectureName'] as String,
      municipalityId: json['municipalityId'] as String,
      municipalityName: json['municipalityName'] as String,
      districtId: json['districtId'] as String,
      districtName: json['districtName'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'prefectureId': prefectureId,
      'prefectureName': prefectureName,
      'municipalityId': municipalityId,
      'municipalityName': municipalityName,
      'districtId': districtId,
      'districtName': districtName,
    };
  }

  /// ヘッダー表示用の地域名（20文字制限付き）
  ///
  /// 「{市区町村名} {地区名}」形式で表示する。
  /// 合計が20文字を超える場合は20文字目まで表示し、省略記号（…）を付与する。
  String get displayName {
    final fullName = '$municipalityName $districtName';
    if (fullName.length > 20) {
      return '${fullName.substring(0, 20)}…';
    }
    return fullName;
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RegionSetting &&
          runtimeType == other.runtimeType &&
          prefectureId == other.prefectureId &&
          prefectureName == other.prefectureName &&
          municipalityId == other.municipalityId &&
          municipalityName == other.municipalityName &&
          districtId == other.districtId &&
          districtName == other.districtName;

  @override
  int get hashCode =>
      prefectureId.hashCode ^
      prefectureName.hashCode ^
      municipalityId.hashCode ^
      municipalityName.hashCode ^
      districtId.hashCode ^
      districtName.hashCode;

  @override
  String toString() =>
      'RegionSetting(prefectureId: $prefectureId, prefectureName: $prefectureName, '
      'municipalityId: $municipalityId, municipalityName: $municipalityName, '
      'districtId: $districtId, districtName: $districtName)';
}
