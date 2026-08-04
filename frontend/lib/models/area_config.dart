// エリア設定構造体と設定レジストリ
// 対応エリア（市区町村）ごとの設定情報を管理する。
// 複数エリア対応のためのリファクタリング基盤。

/// エリア設定構造体
class AreaConfig {
  /// 全国地方公共団体コード（例: "38201"）
  final String areaId;

  /// 市区町村名（例: "松山市"）
  final String municipalityName;

  /// 旧市町名フィルタ値（choumei.csvの旧市町名カラムとの照合に使用）
  final List<String> oldCityNameFilters;

  /// 地区番号最小値
  final int districtMin;

  /// 地区番号最大値
  final int districtMax;

  const AreaConfig({
    required this.areaId,
    required this.municipalityName,
    required this.oldCityNameFilters,
    required this.districtMin,
    required this.districtMax,
  });

  @override
  String toString() =>
      'AreaConfig(areaId: $areaId, municipalityName: $municipalityName, '
      'oldCityNameFilters: $oldCityNameFilters, '
      'districtMin: $districtMin, districtMax: $districtMax)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AreaConfig &&
          runtimeType == other.runtimeType &&
          areaId == other.areaId &&
          municipalityName == other.municipalityName &&
          districtMin == other.districtMin &&
          districtMax == other.districtMax;

  @override
  int get hashCode =>
      Object.hash(areaId, municipalityName, districtMin, districtMax);
}

/// エリア設定レジストリ
///
/// 登録された全エリア設定を管理する静的レジストリ。
/// 新しいエリアを追加する場合は _configs マップにエントリを追加する。
class AreaConfigRegistry {
  AreaConfigRegistry._();

  static const Map<String, AreaConfig> _configs = {
    '38201': AreaConfig(
      areaId: '38201',
      municipalityName: '松山市',
      oldCityNameFilters: ['旧松山市', '旧北条市', '旧中島町'],
      districtMin: 1,
      districtMax: 84,
    ),
    '38202': AreaConfig(
      areaId: '38202',
      municipalityName: '今治市',
      oldCityNameFilters: [
        '旧今治市',
        '旧朝倉村',
        '旧玉川町',
        '旧波方町',
        '旧大西町',
        '旧菊間町',
        '旧吉海町',
        '旧宮窪町',
        '旧伯方町',
        '旧上浦町',
        '旧大三島町',
        '旧関前村',
      ],
      districtMin: 1,
      districtMax: 44,
    ),
    '38203': AreaConfig(
      areaId: '38203',
      municipalityName: '宇和島市',
      oldCityNameFilters: [
        '旧宇和島市',
        '旧吉田町',
        '旧三間町',
        '旧津島町',
      ],
      districtMin: 1,
      districtMax: 4,
    ),
    '38204': AreaConfig(
      areaId: '38204',
      municipalityName: '八幡浜市',
      oldCityNameFilters: [
        '旧八幡浜市',
        '旧保内町',
      ],
      districtMin: 1,
      districtMax: 126,
    ),
  };

  /// エリアIDから設定を取得する。未登録の場合はnullを返す。
  static AreaConfig? getConfig(String areaId) => _configs[areaId];

  /// 登録された全エリア設定をリストで返す。
  static List<AreaConfig> getAll() => _configs.values.toList();
}
