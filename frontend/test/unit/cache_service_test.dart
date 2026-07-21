import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:garbage_app/services/cache_service.dart';

void main() {
  late CacheService cacheService;

  setUp(() {
    // テスト用にSharedPreferencesのモックを初期化
    SharedPreferences.setMockInitialValues({});
    cacheService = CacheService();
  });

  group('CacheService.setLastUpdated', () {
    test('日時をISO8601形式で保存できる', () async {
      final dateTime = DateTime(2024, 6, 15, 10, 30, 0);
      await cacheService.setLastUpdated(dateTime);

      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getString('data_last_updated');
      expect(stored, equals(dateTime.toIso8601String()));
    });

    test('上書き保存が正しく動作する', () async {
      final firstDate = DateTime(2024, 1, 1);
      final secondDate = DateTime(2024, 6, 15);

      await cacheService.setLastUpdated(firstDate);
      await cacheService.setLastUpdated(secondDate);

      final result = await cacheService.getLastUpdated();
      expect(result, equals(secondDate));
    });
  });

  group('CacheService.getLastUpdated', () {
    test('未設定の場合はnullを返す', () async {
      final result = await cacheService.getLastUpdated();
      expect(result, isNull);
    });

    test('保存済みの日時を正しく復元できる', () async {
      final dateTime = DateTime(2024, 3, 20, 14, 0, 0);
      await cacheService.setLastUpdated(dateTime);

      final result = await cacheService.getLastUpdated();
      expect(result, equals(dateTime));
    });
  });

  group('CacheService.isDataExpired', () {
    test('最終更新日時が未設定の場合はtrueを返す', () async {
      final result = await cacheService.isDataExpired();
      expect(result, isTrue);
    });

    test('30日以上経過している場合はtrueを返す', () async {
      final lastUpdated = DateTime(2024, 1, 1);
      await cacheService.setLastUpdated(lastUpdated);

      final now = DateTime(2024, 2, 1); // 31日後
      final result = await cacheService.isDataExpired(now: now);
      expect(result, isTrue);
    });

    test('ちょうど30日経過している場合はtrueを返す', () async {
      final lastUpdated = DateTime(2024, 1, 1);
      await cacheService.setLastUpdated(lastUpdated);

      final now = DateTime(2024, 1, 31); // 30日後
      final result = await cacheService.isDataExpired(now: now);
      expect(result, isTrue);
    });

    test('29日経過の場合はfalseを返す', () async {
      final lastUpdated = DateTime(2024, 1, 1);
      await cacheService.setLastUpdated(lastUpdated);

      final now = DateTime(2024, 1, 30); // 29日後
      final result = await cacheService.isDataExpired(now: now);
      expect(result, isFalse);
    });

    test('同日の場合はfalseを返す', () async {
      final now = DateTime(2024, 6, 15);
      await cacheService.setLastUpdated(now);

      final result = await cacheService.isDataExpired(now: now);
      expect(result, isFalse);
    });
  });
}
