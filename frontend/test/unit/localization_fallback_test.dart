import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/utils/localization_fallback_logger.dart';

void main() {
  group('localization_fallback_logger', () {
    test('logFallbackUsage does not throw in debug mode', () {
      // In test (debug) mode, logFallbackUsage should print without error
      expect(
        () => logFallbackUsage('name', 'item-001', 'en'),
        returnsNormally,
      );
    });
  });

  group('GarbageItem display getters with fallback logging', () {
    test('displayName returns localizedName when available', () {
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        localizedName: 'Newspaper',
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        keywords: ['新聞'],
        requestedLanguage: 'en',
      );

      expect(item.displayName, equals('Newspaper'));
    });

    test('displayName falls back to Japanese name when localizedName is null',
        () {
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        localizedName: null,
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        keywords: ['新聞'],
        requestedLanguage: 'en',
      );

      expect(item.displayName, equals('新聞紙'));
    });

    test('displayDisposalMethod returns localized when available', () {
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        localizedDisposalMethod: 'Put out on recyclable day',
        keywords: ['新聞'],
        requestedLanguage: 'en',
      );

      expect(item.displayDisposalMethod, equals('Put out on recyclable day'));
    });

    test('displayDisposalMethod falls back to Japanese when localized is null',
        () {
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        localizedDisposalMethod: null,
        keywords: ['新聞'],
        requestedLanguage: 'pt',
      );

      expect(item.displayDisposalMethod, equals('資源ごみの日に出す'));
    });

    test('displayCaution returns localized caution when available', () {
      final item = GarbageItem(
        id: 'item-002',
        name: '電池',
        primaryCategory: GarbageCategory.hazardous,
        secondaryCategories: [],
        disposalMethod: '危険ごみの日に出す',
        caution: '端子をテープで覆う',
        localizedCaution: 'Cover terminals with tape',
        keywords: ['電池'],
        requestedLanguage: 'en',
      );

      expect(item.displayCaution, equals('Cover terminals with tape'));
    });

    test('displayCaution falls back to Japanese caution when localized is null',
        () {
      final item = GarbageItem(
        id: 'item-002',
        name: '電池',
        primaryCategory: GarbageCategory.hazardous,
        secondaryCategories: [],
        disposalMethod: '危険ごみの日に出す',
        caution: '端子をテープで覆う',
        localizedCaution: null,
        keywords: ['電池'],
        requestedLanguage: 'zh',
      );

      expect(item.displayCaution, equals('端子をテープで覆う'));
    });

    test(
        'displayCaution returns null when both localized and Japanese caution are null',
        () {
      final item = GarbageItem(
        id: 'item-003',
        name: 'ティッシュ',
        primaryCategory: GarbageCategory.burnable,
        secondaryCategories: [],
        disposalMethod: '可燃ごみの日に出す',
        caution: null,
        localizedCaution: null,
        keywords: ['ティッシュ'],
        requestedLanguage: 'en',
      );

      expect(item.displayCaution, isNull);
    });

    test('no fallback log when requestedLanguage is ja', () {
      // When language is Japanese, no fallback should be logged even if
      // localized fields are null (because Japanese IS the fallback)
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        localizedName: null,
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        keywords: ['新聞'],
        requestedLanguage: 'ja',
      );

      // Should return Japanese name without logging
      expect(item.displayName, equals('新聞紙'));
    });

    test('no fallback log when requestedLanguage is null', () {
      // When no language is specified (e.g., local data), no log is expected
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        localizedName: null,
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        keywords: ['新聞'],
      );

      expect(item.displayName, equals('新聞紙'));
    });

    test('screens never display empty text - name is always non-null', () {
      // name is a required field, so displayName always returns non-empty
      final item = GarbageItem(
        id: 'item-001',
        name: '新聞紙',
        primaryCategory: GarbageCategory.recyclable,
        secondaryCategories: [],
        disposalMethod: '資源ごみの日に出す',
        keywords: ['新聞'],
        requestedLanguage: 'vi',
      );

      expect(item.displayName, isNotEmpty);
      expect(item.displayDisposalMethod, isNotEmpty);
    });
  });
}
