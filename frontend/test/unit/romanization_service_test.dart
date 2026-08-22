import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/romanization_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late RomanizationService service;

  setUp(() {
    service = RomanizationService.instance;
    service.reset();

    // Mock the asset bundle to provide test data
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMessageHandler('flutter/assets', (ByteData? message) async {
      // Decode the asset key from the message
      final String key = utf8.decode(message!.buffer.asUint8List());
      if (key == 'assets/data/municipality_romanization.json') {
        final data = json.encode({
          '松山市': 'Matsuyama-shi',
          '今治市': 'Imabari-shi',
          '宇和島市': 'Uwajima-shi',
          '八幡浜市': 'Yawatahama-shi',
          '新居浜市': 'Niihama-shi',
          '西条市': 'Saijo-shi',
          '大洲市': 'Ozu-shi',
          '伊予市': 'Iyo-shi',
          '四国中央市': 'Shikokuchuo-shi',
          '西予市': 'Seiyo-shi',
          '東温市': 'Toon-shi',
          '上島町': 'Kamijima-cho',
          '久万高原町': 'Kumakogen-cho',
          '松前町': 'Masaki-cho',
          '砥部町': 'Tobe-cho',
          '内子町': 'Uchiko-cho',
          '伊方町': 'Ikata-cho',
          '松野町': 'Matsuno-cho',
          '鬼北町': 'Kihoku-cho',
          '愛南町': 'Ainan-cho',
        });
        return ByteData.view(utf8.encode(data).buffer);
      }
      return null;
    });
  });

  tearDown(() {
    service.reset();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMessageHandler('flutter/assets', null);
  });

  group('RomanizationService', () {
    test('load() loads data successfully', () async {
      expect(service.isLoaded, isFalse);
      await service.load();
      expect(service.isLoaded, isTrue);
    });

    test('getRomanizedName returns correct romanization after load', () async {
      await service.load();
      expect(service.getRomanizedName('松山市'), equals('Matsuyama-shi'));
      expect(service.getRomanizedName('今治市'), equals('Imabari-shi'));
      expect(service.getRomanizedName('愛南町'), equals('Ainan-cho'));
    });

    test('getRomanizedName returns null for unknown municipality', () async {
      await service.load();
      expect(service.getRomanizedName('東京都'), isNull);
    });

    test('getRomanizedName returns null before load', () {
      expect(service.getRomanizedName('松山市'), isNull);
    });

    test(
        'formatMunicipalityName returns Japanese name only when isJapaneseLocale is true',
        () async {
      await service.load();
      final result = service.formatMunicipalityName(
        '松山市',
        isJapaneseLocale: true,
      );
      expect(result, equals('松山市'));
    });

    test(
        'formatMunicipalityName returns name with romanization when isJapaneseLocale is false',
        () async {
      await service.load();
      final result = service.formatMunicipalityName(
        '松山市',
        isJapaneseLocale: false,
      );
      expect(result, equals('松山市 (Matsuyama-shi)'));
    });

    test(
        'formatMunicipalityName returns Japanese name for unknown municipality when non-Japanese',
        () async {
      await service.load();
      final result = service.formatMunicipalityName(
        '東京都',
        isJapaneseLocale: false,
      );
      expect(result, equals('東京都'));
    });

    test('formatMunicipalityName works for all Ehime municipalities', () async {
      await service.load();
      final expectations = {
        '松山市': 'Matsuyama-shi',
        '今治市': 'Imabari-shi',
        '宇和島市': 'Uwajima-shi',
        '八幡浜市': 'Yawatahama-shi',
        '新居浜市': 'Niihama-shi',
        '西条市': 'Saijo-shi',
        '大洲市': 'Ozu-shi',
        '伊予市': 'Iyo-shi',
        '四国中央市': 'Shikokuchuo-shi',
        '西予市': 'Seiyo-shi',
        '東温市': 'Toon-shi',
        '上島町': 'Kamijima-cho',
        '久万高原町': 'Kumakogen-cho',
        '松前町': 'Masaki-cho',
        '砥部町': 'Tobe-cho',
        '内子町': 'Uchiko-cho',
        '伊方町': 'Ikata-cho',
        '松野町': 'Matsuno-cho',
        '鬼北町': 'Kihoku-cho',
        '愛南町': 'Ainan-cho',
      };

      for (final entry in expectations.entries) {
        final result = service.formatMunicipalityName(
          entry.key,
          isJapaneseLocale: false,
        );
        expect(result, equals('${entry.key} (${entry.value})'),
            reason: 'Failed for municipality: ${entry.key}');
      }
    });

    test('load() is idempotent - second call does not reload', () async {
      await service.load();
      expect(service.isLoaded, isTrue);
      // Second call should not throw or change state
      await service.load();
      expect(service.isLoaded, isTrue);
      expect(service.getRomanizedName('松山市'), equals('Matsuyama-shi'));
    });

    test('reset() clears loaded data', () async {
      await service.load();
      expect(service.isLoaded, isTrue);
      service.reset();
      expect(service.isLoaded, isFalse);
      expect(service.getRomanizedName('松山市'), isNull);
    });
  });
}
