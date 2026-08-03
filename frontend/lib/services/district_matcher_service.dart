import 'package:csv/csv.dart';
import 'package:flutter/services.dart';

import '../models/area_config.dart';
import '../models/gps_detection.dart';
import 'abstract_district_matcher.dart';
import 'address_normalizer.dart';

/// choumei.csvデータと住所情報のマッチングにより地区を判定するサービス。
///
/// 逆ジオコーディングで取得した住所の町名部分をchoumei.csvの町名カラムと照合し、
/// 対応する地区番号・地区名を特定する。
///
/// 段階的マッチング: 原文照合 → 正規化照合 → 前方一致
class DistrictMatcherService extends AbstractDistrictMatcher {
  /// パース済みのchoumei.csvデータのキャッシュ
  List<ChoumeiEntry>? _cachedEntries;

  /// 住所正規化ユーティリティ
  final AddressNormalizer _normalizer = AddressNormalizer();

  /// 候補リストの最大件数
  static const int _maxCandidates = 50;

  /// choumei.csvデータを読み込みキャッシュする。
  ///
  /// 既にキャッシュされている場合は再読み込みしない。
  @override
  Future<void> loadChoumeiData() async {
    if (_cachedEntries != null) return;

    final csvString = await rootBundle.loadString('assets/choumei.csv');
    final rows = const CsvToListConverter().convert(csvString);

    // ヘッダー行をスキップしてパース
    _cachedEntries = rows.skip(1).map((row) {
      return ChoumeiEntry(
        districtNumber: int.parse(row[0].toString().trim()),
        districtName: row[1].toString().trim(),
        townCode: row[2].toString().trim(),
        townName: row[3].toString().trim(),
        oldCityName: row[4].toString().trim(),
      );
    }).toList();
  }

  /// 住所から地区を判定する。
  ///
  /// マッチング手順:
  /// 1. areaIdが指定されている場合はAreaConfigRegistryで検証
  /// 2. [address.city] がAreaConfigのmunicipalityNameと一致することを確認
  /// 3. 段階的マッチング: 原文照合 → 正規化照合 → 前方一致
  ///
  /// [address] マッチング対象の住所
  /// [areaId] エリア識別子（全国地方公共団体コード）。指定時は該当エリアのみフィルタ。
  ///
  /// Throws:
  /// - [StateError] choumeiデータ未ロード
  /// - [ArgumentError] 未登録のareaIdが指定された場合
  /// - [OutOfAreaException] 対応エリア外の場合
  /// - [DistrictNotFoundException] 地区を特定できなかった場合
  @override
  DistrictMatchResult matchDistrict(GeocodedAddress address, {String? areaId}) {
    if (_cachedEntries == null) {
      throw StateError('choumei data not loaded. Call loadChoumeiData() first.');
    }

    // areaIdが指定されている場合はAreaConfigRegistryで検証
    AreaConfig? areaConfig;
    if (areaId != null) {
      areaConfig = AreaConfigRegistry.getConfig(areaId);
      if (areaConfig == null) {
        throw ArgumentError('エリア未登録: $areaId');
      }
    }

    // 市区町村名チェック
    final expectedCity =
        areaConfig?.municipalityName ?? '松山市';
    if (address.city != expectedCity) {
      throw OutOfAreaException();
    }

    // エリアフィルタ適用
    final entries = _getFilteredEntries(areaConfig);

    // 原文テキストを構築
    final rawTownText = _buildTownText(address);

    // === 段階的マッチング ===

    // (1) 原文で完全一致検索
    final rawExactMatch = _findExactMatch(entries, rawTownText);

    // (2) 正規化して完全一致検索
    final normalizedText = _normalizer.normalize(rawTownText);
    final normalizedExactMatch = _findNormalizedExactMatch(entries, normalizedText);

    // 原文と正規化の両方でマッチしたが異なる地区の場合、原文を優先 (Req 4.8)
    if (rawExactMatch != null && normalizedExactMatch != null) {
      return rawExactMatch;
    }

    // 原文マッチがあればそれを返す
    if (rawExactMatch != null) {
      return rawExactMatch;
    }

    // 正規化マッチがあればそれを返す
    if (normalizedExactMatch != null) {
      return normalizedExactMatch;
    }

    // (3) 前方一致検索（正規化済みテキストで）
    final prefixMatches = _findPrefixMatches(entries, normalizedText);

    if (prefixMatches.length == 1) {
      final entry = prefixMatches.first;
      return DistrictMatchResult(
        districtNumber: entry.districtNumber,
        districtName: entry.districtName,
        matchedTown: entry.townName,
      );
    }

    if (prefixMatches.isNotEmpty) {
      // 複数ヒットした場合は最初のエントリを返す（互換性維持）
      final entry = prefixMatches.first;
      return DistrictMatchResult(
        districtNumber: entry.districtNumber,
        districtName: entry.districtName,
        matchedTown: entry.townName,
      );
    }

    // マッチなし
    throw DistrictNotFoundException();
  }

  /// 住所から地区候補リストを返す（複数候補表示用）。
  ///
  /// 前方一致で複数の町名候補がヒットした場合に、
  /// 全候補を [DistrictCandidate] のリストとして返す。
  /// リストは町名（townName）の昇順（Unicode順）でソートされる。
  /// 50件を超える場合は先頭50件のみ返す。
  ///
  /// [address] マッチング対象の住所
  /// [areaId] エリア識別子（全国地方公共団体コード）。指定時は該当エリアのみフィルタ。
  @override
  List<DistrictCandidate> matchDistrictCandidates(
    GeocodedAddress address, {
    String? areaId,
  }) {
    if (_cachedEntries == null) {
      throw StateError('choumei data not loaded. Call loadChoumeiData() first.');
    }

    // areaIdが指定されている場合はAreaConfigRegistryで検証
    AreaConfig? areaConfig;
    if (areaId != null) {
      areaConfig = AreaConfigRegistry.getConfig(areaId);
      if (areaConfig == null) {
        throw ArgumentError('エリア未登録: $areaId');
      }
    }

    // エリアフィルタ適用
    final entries = _getFilteredEntries(areaConfig);

    // 原文テキストを構築
    final rawTownText = _buildTownText(address);

    // 正規化テキスト
    final normalizedText = _normalizer.normalize(rawTownText);

    // 前方一致検索
    final prefixMatches = _findPrefixMatches(entries, normalizedText);

    // DistrictCandidateに変換
    final candidates = prefixMatches
        .map((entry) => DistrictCandidate(
              districtNumber: entry.districtNumber,
              districtName: entry.districtName,
              townName: entry.townName,
            ))
        .toList();

    // townNameの昇順（Unicode順）でソート
    candidates.sort((a, b) => a.townName.compareTo(b.townName));

    // 50件でキャップ
    if (candidates.length > _maxCandidates) {
      return candidates.sublist(0, _maxCandidates);
    }

    return candidates;
  }

  // === Private helper methods ===

  /// エリアフィルタを適用してchoumeiエントリを取得する
  List<ChoumeiEntry> _getFilteredEntries(AreaConfig? areaConfig) {
    final entries = _cachedEntries!;
    if (areaConfig == null) {
      return entries;
    }
    return entries
        .where((entry) =>
            areaConfig.oldCityNameFilters.contains(entry.oldCityName))
        .toList();
  }

  /// 住所からマッチング用の町名テキストを構築する
  String _buildTownText(GeocodedAddress address) {
    if (address.subTown != null && address.subTown!.isNotEmpty) {
      return '${address.town}${address.subTown}';
    }
    return address.town;
  }

  /// 原文テキストで完全一致検索する（数字正規化のみ適用）
  DistrictMatchResult? _findExactMatch(
      List<ChoumeiEntry> entries, String rawText) {
    final normalizedNumbers = _normalizeNumbers(rawText);
    for (final entry in entries) {
      final normalizedEntryTown = _normalizeNumbers(entry.townName);
      if (normalizedEntryTown == normalizedNumbers) {
        return DistrictMatchResult(
          districtNumber: entry.districtNumber,
          districtName: entry.districtName,
          matchedTown: entry.townName,
        );
      }
    }
    return null;
  }

  /// 正規化済みテキストで完全一致検索する
  DistrictMatchResult? _findNormalizedExactMatch(
      List<ChoumeiEntry> entries, String normalizedText) {
    for (final entry in entries) {
      final normalizedEntryTown = _normalizer.normalize(entry.townName);
      if (normalizedEntryTown == normalizedText) {
        return DistrictMatchResult(
          districtNumber: entry.districtNumber,
          districtName: entry.districtName,
          matchedTown: entry.townName,
        );
      }
    }
    return null;
  }

  /// 正規化済みテキストで前方一致検索する
  List<ChoumeiEntry> _findPrefixMatches(
      List<ChoumeiEntry> entries, String normalizedText) {
    final matches = <ChoumeiEntry>[];
    for (final entry in entries) {
      final normalizedEntryTown = _normalizer.normalize(entry.townName);
      if (normalizedEntryTown.startsWith(normalizedText)) {
        matches.add(entry);
      }
    }
    return matches;
  }

  /// 全角数字を半角数字に正規化する（原文照合用）。
  ///
  /// CSVデータは全角数字（例: 「３丁目」）を使用しているが、
  /// 逆ジオコーディング結果は半角数字（例: 「3丁目」）の場合があるため、
  /// 比較前に統一する。
  String _normalizeNumbers(String input) {
    const fullWidthDigits = '０１２３４５６７８９';
    final buffer = StringBuffer();
    for (final char in input.runes) {
      final s = String.fromCharCode(char);
      final index = fullWidthDigits.indexOf(s);
      if (index >= 0) {
        buffer.write(index.toString());
      } else {
        buffer.write(s);
      }
    }
    return buffer.toString();
  }
}
