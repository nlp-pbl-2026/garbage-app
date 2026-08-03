import '../models/gps_detection.dart';

/// 地区マッチングサービスの抽象インターフェース。
///
/// choumei.csvデータと住所情報のマッチングにより地区を判定する。
/// テスト時にモック実装を注入可能にするためのDI基盤。
abstract class AbstractDistrictMatcher {
  /// choumei.csvデータを読み込みキャッシュする。
  Future<void> loadChoumeiData();

  /// 住所から地区を判定する（単一結果）。
  ///
  /// マッチング手順: 原文照合 → 正規化照合 → 前方一致
  /// 単一の一致がある場合に [DistrictMatchResult] を返す。
  ///
  /// [address] マッチング対象の住所
  /// [areaId] エリア識別子（全国地方公共団体コード）。指定時は該当エリアのみフィルタ。
  ///
  /// Throws:
  /// - [OutOfAreaException] 対応エリア外の場合
  /// - [DistrictNotFoundException] 地区を特定できなかった場合
  DistrictMatchResult matchDistrict(GeocodedAddress address, {String? areaId});

  /// 住所から地区候補リストを返す（複数候補表示用）。
  ///
  /// 前方一致で複数の町名候補がヒットした場合に、
  /// 全候補を [DistrictCandidate] のリストとして返す。
  /// リストは町名（townName）の昇順（Unicode順）でソートされる。
  ///
  /// [address] マッチング対象の住所
  /// [areaId] エリア識別子（全国地方公共団体コード）。指定時は該当エリアのみフィルタ。
  List<DistrictCandidate> matchDistrictCandidates(
    GeocodedAddress address, {
    String? areaId,
  });
}
