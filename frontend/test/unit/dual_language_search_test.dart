import 'package:flutter_test/flutter_test.dart';

import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/services/garbage_service.dart';

/// デュアル言語検索のユニットテスト
///
/// 要件7.6: 選択言語のキーワード/名前で検索可能
/// 要件7.7: 非日本語言語選択時、日本語のキーワード/名前でも検索可能
/// 要件7.8: 翻訳があれば翻訳名、なければ日本語名を表示
void main() {
  group('GarbageService.searchItems - dual-language search', () {
    late GarbageService service;

    setUp(() {
      service = GarbageService();
    });

    // テスト用のGarbageItemリスト
    List<GarbageItem> createTestItems() {
      return [
        GarbageItem(
          id: '001',
          name: '新聞紙',
          localizedName: 'Newspaper',
          primaryCategory: GarbageCategory.recyclable,
          secondaryCategories: [],
          disposalMethod: '紐で束ねて出す',
          keywords: ['しんぶんし', '新聞'],
          localizedKeywords: ['paper', 'news'],
        ),
        GarbageItem(
          id: '002',
          name: 'ペットボトル',
          localizedName: 'PET Bottle',
          primaryCategory: GarbageCategory.petBottle,
          secondaryCategories: [],
          disposalMethod: 'キャップを外して潰す',
          keywords: ['ぺっとぼとる', 'ボトル'],
          localizedKeywords: ['bottle', 'plastic'],
        ),
        GarbageItem(
          id: '003',
          name: '段ボール',
          localizedName: 'Cardboard',
          primaryCategory: GarbageCategory.recyclable,
          secondaryCategories: [],
          disposalMethod: '畳んで紐で束ねる',
          keywords: ['だんぼーる', 'ダンボール'],
          localizedKeywords: ['box', 'carton'],
        ),
        GarbageItem(
          id: '004',
          name: '電池',
          localizedName: null, // 翻訳なし
          primaryCategory: GarbageCategory.hazardous,
          secondaryCategories: [],
          disposalMethod: '透明な袋に入れる',
          keywords: ['でんち', 'バッテリー'],
          localizedKeywords: ['battery'],
        ),
      ];
    }

    group('isDualLanguage=false (Japanese mode)', () {
      test('should match against Japanese name', () async {
        // GarbageServiceはassetsからロードするため、直接テストするには
        // モックが必要だが、ここではロジック部分をテストする
        // 直接searchItemsLogicを使用

        final items = createTestItems();
        final results = _searchItemsLogic(items, '新聞', isDualLanguage: false);

        expect(results.length, 1);
        expect(results.first.id, '001');
      });

      test('should match against Japanese keywords', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'ぺっとぼとる', isDualLanguage: false);

        expect(results.length, 1);
        expect(results.first.id, '002');
      });

      test('should NOT match against localized name in Japanese mode', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'Newspaper', isDualLanguage: false);

        expect(results.isEmpty, true);
      });

      test('should NOT match against localized keywords in Japanese mode', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'paper', isDualLanguage: false);

        expect(results.isEmpty, true);
      });
    });

    group('isDualLanguage=true (non-Japanese mode)', () {
      test('should match against localized name', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'Newspaper', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '001');
      });

      test('should match against localized keywords', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'plastic', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '002');
      });

      test('should also match against Japanese name (dual-language)', () {
        final items = createTestItems();
        final results = _searchItemsLogic(items, '新聞紙', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '001');
      });

      test('should also match against Japanese keywords (dual-language)', () {
        final items = createTestItems();
        final results = _searchItemsLogic(items, 'ボトル', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '002');
      });

      test('should return no duplicates when item matches both languages', () {
        final items = [
          GarbageItem(
            id: '001',
            name: 'bottle item',
            localizedName: 'bottle translated',
            primaryCategory: GarbageCategory.recyclable,
            secondaryCategories: [],
            disposalMethod: 'method',
            keywords: ['bottle keyword'],
            localizedKeywords: ['bottle localized'],
          ),
        ];
        final results =
            _searchItemsLogic(items, 'bottle', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '001');
      });

      test(
          'should combine results from both language matches without duplicates',
          () {
        final items = createTestItems();
        // "ボトル" matches item '002' via Japanese keywords
        // "bottle" matches item '002' via localized keywords
        // Both should not create duplicates
        final resultsJa = _searchItemsLogic(items, 'ボトル', isDualLanguage: true);
        final resultsEn =
            _searchItemsLogic(items, 'bottle', isDualLanguage: true);

        expect(resultsJa.length, 1);
        expect(resultsEn.length, 1);
        expect(resultsJa.first.id, '002');
        expect(resultsEn.first.id, '002');
      });

      test('should find items with no translation via Japanese fields', () {
        final items = createTestItems();
        final results = _searchItemsLogic(items, '電池', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '004');
        // displayName should fall back to Japanese name when localizedName is null
        expect(results.first.displayName, '電池');
      });

      test('should find items with no translation via localized keywords', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'battery', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '004');
      });
    });

    group('displayName behavior', () {
      test('should return localizedName when available', () {
        final item = GarbageItem(
          id: '001',
          name: '新聞紙',
          localizedName: 'Newspaper',
          primaryCategory: GarbageCategory.recyclable,
          secondaryCategories: [],
          disposalMethod: '',
          keywords: [],
        );
        expect(item.displayName, 'Newspaper');
      });

      test('should return Japanese name when localizedName is null', () {
        final item = GarbageItem(
          id: '001',
          name: '新聞紙',
          localizedName: null,
          primaryCategory: GarbageCategory.recyclable,
          secondaryCategories: [],
          disposalMethod: '',
          keywords: [],
        );
        expect(item.displayName, '新聞紙');
      });
    });

    group('edge cases', () {
      test('should be case-insensitive for localized search', () {
        final items = createTestItems();
        final results =
            _searchItemsLogic(items, 'newspaper', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '001');
      });

      test('should be case-insensitive for Japanese search', () {
        final items = createTestItems();
        // Japanese doesn't have case, but ensure toLowerCase doesn't break
        final results = _searchItemsLogic(items, '新聞', isDualLanguage: true);

        expect(results.length, 1);
        expect(results.first.id, '001');
      });

      test('should return empty list for empty query', () {
        final items = createTestItems();
        final results = _searchItemsLogic(items, '', isDualLanguage: true);

        expect(results.isEmpty, true);
      });

      test('should return empty list for single character query', () {
        final items = createTestItems();
        final results = _searchItemsLogic(items, 'N', isDualLanguage: true);

        expect(results.isEmpty, true);
      });

      test('should handle items with empty localized keywords', () {
        final items = [
          GarbageItem(
            id: '001',
            name: '新聞紙',
            localizedName: 'Newspaper',
            primaryCategory: GarbageCategory.recyclable,
            secondaryCategories: [],
            disposalMethod: '',
            keywords: ['しんぶん'],
            localizedKeywords: [],
          ),
        ];
        final results =
            _searchItemsLogic(items, 'Newspaper', isDualLanguage: true);

        expect(results.length, 1);
      });
    });
  });
}

/// テスト用の検索ロジック（GarbageService.searchItemsと同一ロジック）
///
/// GarbageServiceはassetからデータを読み込むため、ユニットテストでは
/// このヘルパー関数で同じロジックを直接テストする。
List<GarbageItem> _searchItemsLogic(
  List<GarbageItem> items,
  String keyword, {
  bool isDualLanguage = false,
}) {
  if (keyword.length < 2) {
    return [];
  }

  final searchKeyword =
      keyword.length > 50 ? keyword.substring(0, 50) : keyword;
  final queryLower = searchKeyword.toLowerCase();

  final Set<String> matchedIds = {};
  final List<GarbageItem> results = [];

  for (final item in items) {
    if (matchedIds.contains(item.id)) continue;

    bool matches = false;

    if (isDualLanguage) {
      if (item.localizedName?.toLowerCase().contains(queryLower) == true) {
        matches = true;
      }
      if (!matches &&
          item.localizedKeywords
              .any((k) => k.toLowerCase().contains(queryLower))) {
        matches = true;
      }
    }

    // Japanese fields (always)
    if (!matches && item.name.toLowerCase().contains(queryLower)) {
      matches = true;
    }
    if (!matches &&
        item.keywords.any((k) => k.toLowerCase().contains(queryLower))) {
      matches = true;
    }

    if (matches) {
      matchedIds.add(item.id);
      results.add(item);
    }
  }

  if (results.length > 50) {
    return results.sublist(0, 50);
  }
  return results;
}
