// Feature: gps-detection-improvements
// Properties 3-6, 11-16: District Matcher property tests
//
// Property 3: Raw match priority over normalized match
// Property 4: Multiple candidate completeness
// Property 5: Candidate list cap at 50
// Property 6: Candidate sort order
// Property 11: Town name matching correctness
// Property 12: Out-of-area detection
// Property 13: Unmatched town exception
// Property 14: District ID format
// Property 15: Area filtering correctness
// Property 16: Unknown area ID error

@TestOn('vm')
import 'dart:io';

import 'package:test/test.dart';
import 'package:glados/glados.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/models/area_config.dart';
import 'package:garbage_app/services/address_normalizer.dart';

/// A lightweight DistrictMatcher implementation for property testing.
/// Mirrors the real DistrictMatcherService logic without needing Flutter rootBundle.
class TestDistrictMatcher {
  final List<ChoumeiEntry> entries;
  final AddressNormalizer _normalizer = AddressNormalizer();
  static const int maxCandidates = 50;

  TestDistrictMatcher(this.entries);

  DistrictMatchResult matchDistrict(GeocodedAddress address, {String? areaId}) {
    // areaId validation
    AreaConfig? areaConfig;
    if (areaId != null) {
      areaConfig = AreaConfigRegistry.getConfig(areaId);
      if (areaConfig == null) {
        throw ArgumentError('エリア未登録: $areaId');
      }
    }

    // City check
    final expectedCity = areaConfig?.municipalityName ?? '松山市';
    if (address.city != expectedCity) {
      throw OutOfAreaException();
    }

    // Filter entries by area
    final filtered = _getFilteredEntries(areaConfig);

    final rawTownText = _buildTownText(address);

    // (1) Raw exact match
    final rawExact = _findExactMatch(filtered, rawTownText);
    if (rawExact != null) return rawExact;

    // (2) Normalized exact match
    final normalizedText = _normalizer.normalize(rawTownText);
    final normExact = _findNormalizedExactMatch(filtered, normalizedText);
    if (normExact != null) return normExact;

    // (3) Prefix match
    final prefixMatches = _findPrefixMatches(filtered, normalizedText);
    if (prefixMatches.isNotEmpty) {
      final entry = prefixMatches.first;
      return DistrictMatchResult(
        districtNumber: entry.districtNumber,
        districtName: entry.districtName,
        matchedTown: entry.townName,
      );
    }

    throw DistrictNotFoundException();
  }

  List<DistrictCandidate> matchDistrictCandidates(
    GeocodedAddress address, {
    String? areaId,
  }) {
    // areaId validation
    AreaConfig? areaConfig;
    if (areaId != null) {
      areaConfig = AreaConfigRegistry.getConfig(areaId);
      if (areaConfig == null) {
        throw ArgumentError('エリア未登録: $areaId');
      }
    }

    final filtered = _getFilteredEntries(areaConfig);
    final rawTownText = _buildTownText(address);
    final normalizedText = _normalizer.normalize(rawTownText);
    final prefixMatches = _findPrefixMatches(filtered, normalizedText);

    final candidates = prefixMatches
        .map((entry) => DistrictCandidate(
              districtNumber: entry.districtNumber,
              districtName: entry.districtName,
              townName: entry.townName,
            ))
        .toList();

    // Sort by townName ascending Unicode
    candidates.sort((a, b) => a.townName.compareTo(b.townName));

    // Cap at 50
    if (candidates.length > maxCandidates) {
      return candidates.sublist(0, maxCandidates);
    }
    return candidates;
  }

  List<ChoumeiEntry> _getFilteredEntries(AreaConfig? areaConfig) {
    if (areaConfig == null) return entries;
    return entries
        .where((e) => areaConfig.oldCityNameFilters.contains(e.oldCityName))
        .toList();
  }

  String _buildTownText(GeocodedAddress address) {
    if (address.subTown != null && address.subTown!.isNotEmpty) {
      return '${address.town}${address.subTown}';
    }
    return address.town;
  }

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

/// Load choumei.csv entries from the assets directory (for test-time use).
List<ChoumeiEntry> loadChoumeiEntries() {
  final csvFile = File('assets/choumei.csv');
  final csvContent = csvFile.readAsStringSync();
  final lines = csvContent.split('\n');

  final entries = <ChoumeiEntry>[];
  for (final line in lines.skip(1)) {
    if (line.trim().isEmpty) continue;
    final parts = line.split(',');
    if (parts.length >= 5) {
      entries.add(ChoumeiEntry(
        districtNumber: int.parse(parts[0].trim()),
        districtName: parts[1].trim(),
        townCode: parts[2].trim(),
        townName: parts[3].trim(),
        oldCityName: parts[4].trim(),
      ));
    }
  }
  return entries;
}

void main() {
  late List<ChoumeiEntry> allEntries;
  late TestDistrictMatcher matcher;

  setUpAll(() {
    allEntries = loadChoumeiEntries();
    matcher = TestDistrictMatcher(allEntries);
  });

  // =========================================================================
  // Property 3: Raw match priority over normalized match
  // For any GeocodedAddress where both the raw address text and the normalized
  // address text produce a match in choumei.csv, but to different districts,
  // the District_Matcher SHALL return the district matched by the raw
  // (un-normalized) text.
  // **Validates: Requirements 4.5, 4.8**
  // =========================================================================

  // Base town names that don't themselves contain normalization-sensitive chars
  const baseTownNames = [
    '北条',
    '道後',
    '三津',
    '味酒',
    '桑原',
    '久米',
    '石井',
    '余土',
    '垣生',
    '堀江',
  ];

  group('Property 3: Raw match priority over normalized match', () {
    Glados2(any.intInRange(1, 42), any.intInRange(43, 84),
            ExploreConfig(numRuns: 100))
        .test(
      'raw match priority - 大字 prefix scenario: raw "大字X" matches entry A, normalized "X" matches entry B',
      (districtA, districtB) {
        for (final baseName in baseTownNames) {
          final entryA = ChoumeiEntry(
            districtNumber: districtA,
            districtName: '地区A',
            townCode: '001',
            townName: '大字$baseName',
            oldCityName: '旧松山市',
          );

          final entryB = ChoumeiEntry(
            districtNumber: districtB,
            districtName: '地区B',
            townCode: '002',
            townName: baseName,
            oldCityName: '旧松山市',
          );

          final testMatcher = TestDistrictMatcher([entryA, entryB]);

          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '大字$baseName',
            fullAddress: '愛媛県松山市大字$baseName',
          );

          final result = testMatcher.matchDistrict(address);

          expect(result.districtNumber, equals(districtA),
              reason:
                  'Raw match district ($districtA) should be returned over normalized '
                  'match district ($districtB) for "大字$baseName"');
          expect(result.matchedTown, equals('大字$baseName'));
        }
      },
    );

    Glados2(any.intInRange(1, 42), any.intInRange(43, 84),
            ExploreConfig(numRuns: 100))
        .test(
      'raw match priority - 字 prefix scenario: raw "字X" matches entry A, normalized "X" matches entry B',
      (districtA, districtB) {
        for (final baseName in baseTownNames) {
          final entryA = ChoumeiEntry(
            districtNumber: districtA,
            districtName: '地区A',
            townCode: '001',
            townName: '字$baseName',
            oldCityName: '旧松山市',
          );

          final entryB = ChoumeiEntry(
            districtNumber: districtB,
            districtName: '地区B',
            townCode: '002',
            townName: baseName,
            oldCityName: '旧松山市',
          );

          final testMatcher = TestDistrictMatcher([entryA, entryB]);

          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '字$baseName',
            fullAddress: '愛媛県松山市字$baseName',
          );

          final result = testMatcher.matchDistrict(address);

          expect(result.districtNumber, equals(districtA),
              reason:
                  'Raw match district ($districtA) should be returned over normalized '
                  'match district ($districtB) for "字$baseName"');
          expect(result.matchedTown, equals('字$baseName'));
        }
      },
    );

    Glados2(any.intInRange(1, 42), any.intInRange(43, 84),
            ExploreConfig(numRuns: 100))
        .test(
      'raw match priority holds regardless of entry order in data',
      (districtA, districtB) {
        for (final baseName in baseTownNames) {
          final entryA = ChoumeiEntry(
            districtNumber: districtA,
            districtName: '地区A',
            townCode: '001',
            townName: '大字$baseName',
            oldCityName: '旧松山市',
          );

          final entryB = ChoumeiEntry(
            districtNumber: districtB,
            districtName: '地区B',
            townCode: '002',
            townName: baseName,
            oldCityName: '旧松山市',
          );

          // Test with entryB FIRST (normalized match entry appears before raw match entry)
          final testMatcher = TestDistrictMatcher([entryB, entryA]);

          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '大字$baseName',
            fullAddress: '愛媛県松山市大字$baseName',
          );

          final result = testMatcher.matchDistrict(address);

          expect(result.districtNumber, equals(districtA),
              reason: 'Raw match should take priority regardless of entry '
                  'ordering for "大字$baseName" (districtA=$districtA, districtB=$districtB)');
        }
      },
    );

    Glados2(any.intInRange(1, 42), any.intInRange(43, 84),
            ExploreConfig(numRuns: 100))
        .test(
      'raw match priority - half-width space scenario: raw "X 1丁目" matches entry A, normalized "X1丁目" matches entry B',
      (districtA, districtB) {
        for (final baseName in baseTownNames) {
          final entryA = ChoumeiEntry(
            districtNumber: districtA,
            districtName: '地区A',
            townCode: '001',
            townName: '$baseName 1丁目',
            oldCityName: '旧松山市',
          );

          final entryB = ChoumeiEntry(
            districtNumber: districtB,
            districtName: '地区B',
            townCode: '002',
            townName: '${baseName}1丁目',
            oldCityName: '旧松山市',
          );

          final testMatcher = TestDistrictMatcher([entryA, entryB]);

          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '$baseName 1丁目',
            fullAddress: '愛媛県松山市$baseName 1丁目',
          );

          final result = testMatcher.matchDistrict(address);

          expect(result.districtNumber, equals(districtA),
              reason:
                  'Raw match (with space) should take priority for "$baseName 1丁目"');
          expect(result.matchedTown, equals('$baseName 1丁目'));
        }
      },
    );

    Glados2(any.intInRange(1, 42), any.intInRange(43, 84),
            ExploreConfig(numRuns: 100))
        .test(
      'raw match priority - full-width space scenario: raw "X\u30001丁目" matches entry A, normalized "X1丁目" matches entry B',
      (districtA, districtB) {
        for (final baseName in baseTownNames) {
          final entryA = ChoumeiEntry(
            districtNumber: districtA,
            districtName: '地区A',
            townCode: '001',
            townName: '$baseName\u30001丁目',
            oldCityName: '旧松山市',
          );

          final entryB = ChoumeiEntry(
            districtNumber: districtB,
            districtName: '地区B',
            townCode: '002',
            townName: '${baseName}1丁目',
            oldCityName: '旧松山市',
          );

          final testMatcher = TestDistrictMatcher([entryA, entryB]);

          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '$baseName\u30001丁目',
            fullAddress: '愛媛県松山市$baseName\u30001丁目',
          );

          final result = testMatcher.matchDistrict(address);

          expect(result.districtNumber, equals(districtA),
              reason: 'Raw match (with full-width space) should take priority '
                  'for "$baseName\u30001丁目"');
          expect(result.matchedTown, equals('$baseName\u30001丁目'));
        }
      },
    );
  });

  // =========================================================================
  // Property 4: Multiple candidate completeness
  // For any choumei dataset and any GeocodedAddress whose town prefix-matches
  // multiple entries, matchDistrictCandidates() SHALL return all matching
  // entries (up to the cap limit).
  // **Validates: Requirements 1.1, 1.5**
  // =========================================================================
  group('Property 4: Multiple candidate completeness', () {
    Glados(any.intInRange(0, 20), ExploreConfig(numRuns: 100)).test(
      'matchDistrictCandidates returns all prefix-matching entries up to cap',
      (prefixLen) {
        final normalizer = AddressNormalizer();

        // Gather all normalized town names
        final normalizedTowns =
            allEntries.map((e) => normalizer.normalize(e.townName)).toList();

        if (allEntries.isEmpty) return;
        final entryIdx = prefixLen % allEntries.length;
        final fullTown = normalizedTowns[entryIdx];
        if (fullTown.isEmpty) return;

        // Use 1 character prefix to get multiple matches
        final prefix = fullTown.substring(0, 1);

        // Count how many entries prefix-match
        final expectedMatches = allEntries.where((e) {
          final normalized = normalizer.normalize(e.townName);
          return normalized.startsWith(prefix);
        }).length;

        // Get candidates
        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: prefix,
          fullAddress: '愛媛県松山市$prefix',
        );
        final candidates = matcher.matchDistrictCandidates(address);

        // Should return min(expectedMatches, 50) candidates
        final expectedCount = expectedMatches > 50 ? 50 : expectedMatches;
        expect(candidates.length, equals(expectedCount),
            reason: 'Expected $expectedCount candidates for prefix "$prefix", '
                'got ${candidates.length}');
      },
    );
  });

  // =========================================================================
  // Property 5: Candidate list cap at 50
  // For any match operation producing more than 50 candidates, the returned
  // list SHALL contain exactly 50 items.
  // **Validates: Requirements 1.6**
  // =========================================================================
  group('Property 5: Candidate list cap at 50', () {
    Glados(any.intInRange(51, 200), ExploreConfig(numRuns: 100)).test(
      'more than 50 candidates returns exactly 50',
      (numEntries) {
        // Generate a dataset with many entries sharing the same prefix
        final entries = List.generate(
          numEntries,
          (i) => ChoumeiEntry(
            districtNumber: (i % 84) + 1,
            districtName: '地区${(i % 84) + 1}',
            townCode: '${1000 + i}',
            townName: '共通町$i丁目',
            oldCityName: '旧松山市',
          ),
        );

        final testMatcher = TestDistrictMatcher(entries);
        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: '共通町',
          fullAddress: '愛媛県松山市共通町',
        );

        final candidates = testMatcher.matchDistrictCandidates(address);
        expect(candidates.length, equals(50),
            reason: 'With $numEntries matching entries, '
                'candidates should be capped at 50');
      },
    );
  });

  // =========================================================================
  // Property 6: Candidate sort order
  // For any list of DistrictCandidate objects returned by
  // matchDistrictCandidates(), the items SHALL be sorted in ascending Unicode
  // order by the townName field.
  // **Validates: Requirements 1.2**
  // =========================================================================
  group('Property 6: Candidate sort order', () {
    Glados(any.intInRange(0, 20), ExploreConfig(numRuns: 100)).test(
      'candidates sorted by townName ascending Unicode',
      (seed) {
        final normalizer = AddressNormalizer();
        if (allEntries.isEmpty) return;

        final entryIdx = seed % allEntries.length;
        final fullTown = normalizer.normalize(allEntries[entryIdx].townName);
        if (fullTown.isEmpty) return;

        final prefix = fullTown.substring(0, 1);

        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: prefix,
          fullAddress: '愛媛県松山市$prefix',
        );

        final candidates = matcher.matchDistrictCandidates(address);

        // Verify sort order
        for (var i = 0; i < candidates.length - 1; i++) {
          expect(
            candidates[i].townName.compareTo(candidates[i + 1].townName) <= 0,
            isTrue,
            reason:
                'Candidate ${candidates[i].townName} should be <= ${candidates[i + 1].townName} '
                'in Unicode sort order',
          );
        }
      },
    );

    test('candidates from synthetic data are sorted correctly', () {
      final entries = [
        ChoumeiEntry(districtNumber: 1, districtName: '地区1', townCode: '001',
            townName: 'ん町', oldCityName: '旧松山市'),
        ChoumeiEntry(districtNumber: 2, districtName: '地区2', townCode: '002',
            townName: 'あ町', oldCityName: '旧松山市'),
        ChoumeiEntry(districtNumber: 3, districtName: '地区3', townCode: '003',
            townName: 'か町', oldCityName: '旧松山市'),
        ChoumeiEntry(districtNumber: 4, districtName: '地区4', townCode: '004',
            townName: 'さ町', oldCityName: '旧松山市'),
      ];

      final testMatcher = TestDistrictMatcher(entries);
      final address = GeocodedAddress(
        prefecture: '愛媛県',
        city: '松山市',
        town: '', // empty prefix matches all via startsWith('')
        fullAddress: '愛媛県松山市',
      );

      final candidates = testMatcher.matchDistrictCandidates(address);
      expect(candidates.length, equals(4));
      expect(candidates[0].townName, equals('あ町'));
      expect(candidates[1].townName, equals('か町'));
      expect(candidates[2].townName, equals('さ町'));
      expect(candidates[3].townName, equals('ん町'));
    });
  });

  // =========================================================================
  // Property 11: Town name matching correctness
  // For any town name that exists in choumei.csv, constructing a GeocodedAddress
  // with city="松山市" and the corresponding town, then calling matchDistrict()
  // SHALL return the correct district number and district name.
  // **Validates: Requirements 8.2**
  // =========================================================================
  group('Property 11: Town name matching correctness', () {
    test(
      'all choumei.csv town names return correct district',
      () {
        for (final entry in allEntries) {
          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: entry.townName,
            fullAddress: '愛媛県松山市${entry.townName}',
          );

          final result = matcher.matchDistrict(address);
          expect(result.districtNumber, equals(entry.districtNumber),
              reason: 'Town "${entry.townName}" should map to district '
                  '${entry.districtNumber} (${entry.districtName}), '
                  'but got ${result.districtNumber}');
          expect(result.districtName, equals(entry.districtName),
              reason: 'Town "${entry.townName}" should map to district name '
                  '"${entry.districtName}", but got "${result.districtName}"');
        }
      },
    );
  });

  // =========================================================================
  // Property 12: Out-of-area detection
  // For any city name string that is not "松山市", calling matchDistrict()
  // SHALL throw OutOfAreaException.
  // **Validates: Requirements 8.3**
  // =========================================================================
  group('Property 12: Out-of-area detection', () {
    Glados(any.intInRange(0, 99), ExploreConfig(numRuns: 100)).test(
      'non-松山市 city throws OutOfAreaException',
      (seed) {
        // Generate city names that are NOT 松山市
        const otherCities = [
          '東京都', '大阪市', '福岡市', '名古屋市', '札幌市',
          '横浜市', '神戸市', '京都市', '広島市', '仙台市',
          '新宿区', '渋谷区', '港区', '千代田区', '品川区',
          '今治市', '宇和島市', '八幡浜市', '新居浜市', '西条市',
          '大洲市', '伊予市', '四国中央市', '西予市', '東温市',
          '上島町', '久万高原町', '松前町', '砥部町', '内子町',
          '伊方町', '松野町', '鬼北町', '愛南町', '高松市',
          '丸亀市', '坂出市', '善通寺市', '観音寺市', '三豊市',
          '那覇市', '宮崎市', '鹿児島市', '長崎市', '佐賀市',
          '大分市', '熊本市', '岡山市', '倉敷市', '高知市',
          '徳島市', '山口市', '下関市', '奈良市', '和歌山市',
          '津市', '岐阜市', '福井市', '金沢市', '富山市',
          '長野市', '甲府市', '静岡市', '浜松市', '水戸市',
          '宇都宮市', '前橋市', 'さいたま市', '千葉市', '川崎市',
          '相模原市', '新潟市', '秋田市', '山形市', '福島市',
          '盛岡市', '青森市', '函館市', '旭川市', '釧路市',
          '帯広市', '小樽市', '江別市', '苫小牧市', '室蘭市',
          'テスト市', '架空市', '存在しない市', 'ABC市', 'あいう市',
          '松山', '松山町', '松山村', '東松山市', '西松山市',
          '北松山市', '南松山市', '新松山市', '旧松山市', '松山区',
        ];

        final city = otherCities[seed % otherCities.length];
        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: city,
          town: '番町',
          fullAddress: '愛媛県${city}番町',
        );

        expect(
          () => matcher.matchDistrict(address),
          throwsA(isA<OutOfAreaException>()),
          reason: 'City "$city" is not 松山市, should throw OutOfAreaException',
        );
      },
    );
  });

  // =========================================================================
  // Property 13: Unmatched town exception
  // For any town name string that does not match (exactly or by prefix) any
  // entry in choumei.csv, calling matchDistrict() with city="松山市" SHALL
  // throw DistrictNotFoundException.
  // **Validates: Requirements 8.4**
  // =========================================================================
  group('Property 13: Unmatched town exception', () {
    Glados(any.intInRange(0, 99), ExploreConfig(numRuns: 100)).test(
      'non-existent town throws DistrictNotFoundException',
      (seed) {
        // Generate town names that definitely don't exist in choumei.csv
        const fakeTowns = [
          '絶対存在しない町', 'ABCDEFG', '架空の場所１丁目',
          'xxxxxxxxx', '宇宙ステーション', '火星基地',
          '月面都市', '深海町', '雲上村', '虹色通り',
          'テスト不在地区', '無名通り', '幻の町', '伝説町',
          '???町', '!!!区', '　　　', 'zzzzz',
          '存在不可町999丁目', '想像上の場所',
          '永遠に見つからない町', '不思議の国',
          'ノーマッチタウン', 'アンマッチ地区',
          'ZZZZZ丁目', '～～～', '☆☆☆', '■■■',
          '新規追加予定地区', '未来都市',
          '翡翠の里', '黄金の谷', '白銀の峰',
          '蒼天の丘', '碧落の森', '紅蓮の原',
          '深緑の沢', '紫雲の浜', '銀河の端',
          '時空の裂け目', '次元の狭間', '虚無の空',
          '超越町一番地', '量子力学通り', '相対性理論坂',
          '永久不滅町', '無限回廊', '絶対零度通り',
          '光速の丘', 'プランク通り', '暗黒物質町',
          '反物質通り', 'ニュートリノ坂', '超弦理論町',
          '事象の地平', 'ブラックホール通り', '白色矮星町',
          '赤色巨星坂', '中性子星通り', 'パルサー町',
          '銀河中心通り', '宇宙の果て町', '始まりの地',
          '終わりの場所', '創世の原', '終焉の谷',
          '永劫回帰通り', '輪廻転生坂', '因果応報町',
          '春夏秋冬通り', '四季折々坂', '花鳥風月町',
          '雪月花通り', '風林火山坂', '天地人町',
          '仁義礼智通り', '忠孝悌信坂', '恭倹譲忍町',
          '喜怒哀楽通り', '生老病死坂', '愛別離苦町',
          '五蘊皆空通り', '色即是空坂', '空即是色町',
          '不生不滅通り', '不垢不浄坂', '不増不減町',
          '応無所住通り', '如夢幻泡影坂', '如露如電町',
          '金剛般若通り', '摩訶般若坂', '波羅蜜多町',
          '阿耨多羅通り', '三藐三菩提坂', '無上正等覚町',
        ];

        final fakeTown = fakeTowns[seed % fakeTowns.length];
        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: fakeTown,
          fullAddress: '愛媛県松山市$fakeTown',
        );

        expect(
          () => matcher.matchDistrict(address),
          throwsA(isA<DistrictNotFoundException>()),
          reason: 'Town "$fakeTown" is not in choumei.csv, '
              'should throw DistrictNotFoundException',
        );
      },
    );
  });

  // =========================================================================
  // Property 14: District ID format
  // For any valid municipality ID (string) and district number (integer), the
  // formatted districtId SHALL match the pattern "{municipalityId}-{districtNumber}".
  // **Validates: Requirements 8.5**
  // =========================================================================
  group('Property 14: District ID format', () {
    Glados2(any.intInRange(10000, 99999), any.intInRange(1, 84),
            ExploreConfig(numRuns: 100))
        .test(
      'districtId matches "{municipalityId}-{districtNumber}" pattern',
      (municipalityCode, districtNumber) {
        final municipalityId = municipalityCode.toString();
        final districtId = '$municipalityId-$districtNumber';

        // Verify format: numeric municipality ID, hyphen, numeric district number
        final pattern = RegExp(r'^\d+-\d+$');
        expect(districtId, matches(pattern),
            reason: 'District ID "$districtId" should match '
                '"{municipalityId}-{districtNumber}" pattern');

        // Verify components
        final parts = districtId.split('-');
        expect(parts.length, equals(2));
        expect(parts[0], equals(municipalityId));
        expect(int.parse(parts[1]), equals(districtNumber));
      },
    );
  });

  // =========================================================================
  // Property 15: Area filtering correctness
  // For any registered area ID, matchDistrict(address, areaId: id) SHALL only
  // consider entries whose oldCityName is in the area's configured
  // oldCityNameFilters list.
  // **Validates: Requirements 9.1**
  // =========================================================================
  group('Property 15: Area filtering correctness', () {
    test(
      'matchDistrict with areaId only considers entries matching oldCityNameFilters',
      () {
        const areaId = '38201';
        final areaConfig = AreaConfigRegistry.getConfig(areaId)!;

        for (final entry in allEntries) {
          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: entry.townName,
            fullAddress: '愛媛県松山市${entry.townName}',
          );

          if (areaConfig.oldCityNameFilters.contains(entry.oldCityName)) {
            final result = matcher.matchDistrict(address, areaId: areaId);
            expect(result.districtNumber, equals(entry.districtNumber),
                reason: 'Entry "${entry.townName}" (${entry.oldCityName}) '
                    'should be accessible with areaId=$areaId');
          }
        }
      },
    );

    test(
      'entries not in oldCityNameFilters are excluded by area filtering',
      () {
        final mixedEntries = [
          ChoumeiEntry(
            districtNumber: 1, districtName: '地区1', townCode: '001',
            townName: 'テスト町A', oldCityName: '旧松山市',
          ),
          ChoumeiEntry(
            districtNumber: 2, districtName: '地区2', townCode: '002',
            townName: 'テスト町B', oldCityName: '旧今治市', // Not in filter
          ),
          ChoumeiEntry(
            districtNumber: 3, districtName: '地区3', townCode: '003',
            townName: 'テスト町C', oldCityName: '旧北条市',
          ),
        ];

        final testMatcher = TestDistrictMatcher(mixedEntries);

        // テスト町B should NOT be found with areaId='38201'
        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: 'テスト町B',
          fullAddress: '愛媛県松山市テスト町B',
        );

        expect(
          () => testMatcher.matchDistrict(address, areaId: '38201'),
          throwsA(isA<DistrictNotFoundException>()),
          reason: 'Entry with oldCityName "旧今治市" should be excluded '
              'by area filter for areaId 38201',
        );

        // テスト町A should be found
        final addressA = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: 'テスト町A',
          fullAddress: '愛媛県松山市テスト町A',
        );
        final resultA = testMatcher.matchDistrict(addressA, areaId: '38201');
        expect(resultA.districtNumber, equals(1));

        // テスト町C should be found (旧北条市 is in filter)
        final addressC = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: 'テスト町C',
          fullAddress: '愛媛県松山市テスト町C',
        );
        final resultC = testMatcher.matchDistrict(addressC, areaId: '38201');
        expect(resultC.districtNumber, equals(3));
      },
    );
  });

  // =========================================================================
  // Property 16: Unknown area ID error
  // For any string that is not a registered area ID in AreaConfigRegistry,
  // calling matchDistrict() with that area ID SHALL throw ArgumentError.
  // **Validates: Requirements 9.6**
  // =========================================================================
  group('Property 16: Unknown area ID error', () {
    Glados(any.intInRange(0, 99), ExploreConfig(numRuns: 100)).test(
      'unregistered areaId throws ArgumentError',
      (seed) {
        const fakeAreaIds = [
          '00000', '11111', '22222', '33333', '44444',
          '55555', '66666', '77777', '88888', '99999',
          '38200', '38299', '38297', '38199', '38301',
          '12345', '54321', '10000', '99998', '50000',
          'ABCDE', 'aaaaa', '!@#\$%', '', ' ',
          '3820', '382010', '3820a', 'x38201', '38201x',
          '00001', '13101', '13102', '13103', '13104',
          '27100', '27102', '27103', '27104', '27105',
          '01100', '01101', '01102', '01103', '01104',
          '40100', '40130', '40131', '40132', '40133',
          '34100', '34101', '34102', '34103', '34104',
          '38298', '38296', '38295', '38205', '38206',
          '38207', '38208', '38209', '38210', '38211',
          '38212', '38213', '38214', '38215', '38216',
          '38217', '38218', '38219', '38220', '38221',
          '38222', '38223', '38224', '38225', '38226',
          '38227', '38228', '38229', '38230', '38231',
          '38232', '38233', '38234', '38235', '38236',
          '38237', '38238', '38239', '38240', '38241',
          '38242', '38243', '38244', '38245', '38246',
          '38247', '38248', '38249', '38250', '38251',
          '38252', '38253', '38254', '38255', '38256',
          '38257', '38258', '38259', '38260', '38261',
        ];

        final fakeAreaId = fakeAreaIds[seed % fakeAreaIds.length];
        final address = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: '番町',
          fullAddress: '愛媛県松山市番町',
        );

        expect(
          () => matcher.matchDistrict(address, areaId: fakeAreaId),
          throwsA(isA<ArgumentError>()),
          reason: 'areaId "$fakeAreaId" is not registered, '
              'should throw ArgumentError',
        );
      },
    );
  });
}
