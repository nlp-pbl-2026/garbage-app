import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/utils/text_utils.dart';

void main() {
  group('TextUtils.isCacheExpired', () {
    test('30日以上経過している場合はtrueを返す', () {
      final lastUpdated = DateTime(2024, 1, 1);
      final now = DateTime(2024, 1, 31); // 30日後
      expect(TextUtils.isCacheExpired(lastUpdated, now: now), isTrue);
    });

    test('ちょうど30日経過している場合はtrueを返す', () {
      final lastUpdated = DateTime(2024, 1, 1);
      final now = DateTime(2024, 1, 31); // 30日後
      expect(TextUtils.isCacheExpired(lastUpdated, now: now), isTrue);
    });

    test('29日経過の場合はfalseを返す', () {
      final lastUpdated = DateTime(2024, 1, 1);
      final now = DateTime(2024, 1, 30); // 29日後
      expect(TextUtils.isCacheExpired(lastUpdated, now: now), isFalse);
    });

    test('同日の場合はfalseを返す', () {
      final lastUpdated = DateTime(2024, 6, 15);
      final now = DateTime(2024, 6, 15);
      expect(TextUtils.isCacheExpired(lastUpdated, now: now), isFalse);
    });

    test('1日経過の場合はfalseを返す', () {
      final lastUpdated = DateTime(2024, 3, 1);
      final now = DateTime(2024, 3, 2);
      expect(TextUtils.isCacheExpired(lastUpdated, now: now), isFalse);
    });

    test('大幅に経過している場合（90日）はtrueを返す', () {
      final lastUpdated = DateTime(2024, 1, 1);
      final now = DateTime(2024, 4, 1); // 約90日後
      expect(TextUtils.isCacheExpired(lastUpdated, now: now), isTrue);
    });

    test('nowを指定しない場合はDateTime.now()を使用する', () {
      // 十分過去の日付を使えば必ずtrueになるはず
      final veryOldDate = DateTime(2020, 1, 1);
      expect(TextUtils.isCacheExpired(veryOldDate), isTrue);
    });
  });
}
