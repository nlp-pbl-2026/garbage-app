import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/address_normalizer.dart';

void main() {
  late AddressNormalizer normalizer;

  setUp(() {
    normalizer = AddressNormalizer();
  });

  group('AddressNormalizer.normalize', () {
    group('Step 1: 「大字」除去', () {
      test('「大字」プレフィックスを除去する', () {
        expect(normalizer.normalize('大字北条'), equals('北条'));
      });

      test('「大字」が中間にある場合も除去する', () {
        expect(normalizer.normalize('松山市大字北条'), equals('松山市北条'));
      });

      test('「大字」が含まれない場合は変更しない', () {
        expect(normalizer.normalize('北条'), equals('北条'));
      });
    });

    group('Step 2: 「字」除去', () {
      test('先頭の「字」プレフィックスを除去する', () {
        expect(normalizer.normalize('字鶴吉'), equals('鶴吉'));
      });

      test('「大字」除去後に先頭になる「字」を除去する', () {
        // 「大字字鶴吉」→ Step1で「字鶴吉」→ Step2で「鶴吉」
        expect(normalizer.normalize('大字字鶴吉'), equals('鶴吉'));
      });

      test('町名内部の「字」は保持する', () {
        // 「文字」の「字」は除去しない
        expect(normalizer.normalize('文字町'), equals('文字町'));
      });

      test('先頭でない「字」は保持する', () {
        expect(normalizer.normalize('北条字'), equals('北条字'));
      });
    });

    group('Step 3: スペース除去', () {
      test('全角スペース（U+3000）を除去する', () {
        expect(normalizer.normalize('松山市\u3000北条'), equals('松山市北条'));
      });

      test('半角スペース（U+0020）を除去する', () {
        expect(normalizer.normalize('松山市 北条'), equals('松山市北条'));
      });

      test('複数のスペースを全て除去する', () {
        expect(
          normalizer.normalize('松山市\u3000北条 1丁目'),
          equals('松山市北条1丁目'),
        );
      });
    });

    group('Step 4: 全角数字→半角数字変換', () {
      test('全角数字を半角に変換する', () {
        expect(normalizer.normalize('北条１丁目'), equals('北条1丁目'));
      });

      test('複数の全角数字を半角に変換する', () {
        expect(normalizer.normalize('番町１２３'), equals('番町123'));
      });

      test('全ての全角数字（０〜９）を変換する', () {
        expect(
          normalizer.normalize('０１２３４５６７８９'),
          equals('0123456789'),
        );
      });

      test('半角数字はそのまま保持する', () {
        expect(normalizer.normalize('北条1丁目'), equals('北条1丁目'));
      });
    });

    group('パイプライン（複合テスト）', () {
      test('全ステップを正しい順序で適用する', () {
        // 「大字字　北条　１丁目」
        // Step1: 「字　北条　１丁目」（「大字」除去）
        // Step2: 「　北条　１丁目」（先頭「字」除去）
        // Step3: 「北条１丁目」（スペース除去）
        // Step4: 「北条1丁目」（全角→半角）
        expect(
          normalizer.normalize('大字字\u3000北条\u3000１丁目'),
          equals('北条1丁目'),
        );
      });

      test('変換不要な文字列はそのまま返す', () {
        expect(normalizer.normalize('番町'), equals('番町'));
      });

      test('空文字列を渡すとそのまま空文字列を返す', () {
        expect(normalizer.normalize(''), equals(''));
      });
    });
  });

  group('AddressNormalizer.normalizeSafe', () {
    test('nullの場合は空文字列を返す', () {
      expect(normalizer.normalizeSafe(null), equals(''));
    });

    test('空文字列の場合は空文字列を返す', () {
      expect(normalizer.normalizeSafe(''), equals(''));
    });

    test('通常の文字列の場合はnormalize()と同じ結果を返す', () {
      expect(normalizer.normalizeSafe('大字北条'), equals('北条'));
    });

    test('スペースのみの文字列は正規化を実行する', () {
      // スペースのみは空ではないのでnormalize()を実行し、スペースが除去される
      expect(normalizer.normalizeSafe(' '), equals(''));
    });

    test('全角スペースのみの文字列は正規化を実行する', () {
      expect(normalizer.normalizeSafe('\u3000'), equals(''));
    });
  });
}
