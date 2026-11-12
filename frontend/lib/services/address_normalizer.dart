/// 住所文字列の正規化を行うユーティリティクラス。
///
/// 逆ジオコーディング結果とchoumei.csvの町名データとのマッチング精度を
/// 向上させるために、住所表記のバリエーション（大字/字プレフィックス、スペース、
/// 全角数字）を統一する。
///
/// 純粋関数として実装されており、副作用を持たない。
class AddressNormalizer {
  /// 住所文字列を正規化する。
  ///
  /// 処理順:
  /// 1. 「大字」プレフィックスの除去
  /// 2. 「字」プレフィックスの除去（「大字」除去後の文字列に適用）
  /// 3. スペース除去（全角U+3000・半角U+0020）
  /// 4. 全角数字（U+FF10〜U+FF19）→ 半角数字（U+0030〜U+0039）変換
  String normalize(String input) {
    var result = input;

    // Step 1: 「大字」プレフィックスを除去
    result = _removeOoaza(result);

    // Step 2: 「字」プレフィックスを除去（Step 1の結果に適用）
    result = _removeAza(result);

    // Step 3: 全角スペース（U+3000）と半角スペース（U+0020）を除去
    result = _removeSpaces(result);

    // Step 4: 全角数字を半角数字に変換
    result = _convertFullWidthDigits(result);

    // Step 5: 漢数字（一〜十）を半角数字に変換
    // Nominatimが「二番町四丁目」のように漢数字で返す場合に対応
    result = _convertKanjiDigits(result);

    return result;
  }

  /// null/空文字チェック付き正規化。
  ///
  /// [input] が null または空文字列の場合は空文字列を返し、
  /// 正規化処理をスキップする。
  String normalizeSafe(String? input) {
    if (input == null || input.isEmpty) {
      return '';
    }
    return normalize(input);
  }

  /// 「大字」プレフィックスを除去する。
  ///
  /// 町名の直前に出現する「大字」を除去する。
  /// 例: "大字北条" → "北条"
  String _removeOoaza(String input) {
    return input.replaceAll('大字', '');
  }

  /// 「字」プレフィックスを除去する。
  ///
  /// 町名の直前に出現する独立した「字」プレフィックスを除去する。
  /// 「大字」除去後の文字列に対して適用するため、
  /// 「大字」の一部としての「字」は既に除去済みとなっている。
  ///
  /// 注意: 先頭の「字」のみ除去する。町名内部の「字」（例: 「文字」「漢字」）は
  /// 保持する。
  String _removeAza(String input) {
    // 先頭に「字」がある場合のみ除去（町名プレフィックスとしての「字」）
    if (input.startsWith('字')) {
      return input.substring(1);
    }
    return input;
  }

  /// 全角スペース（U+3000）と半角スペース（U+0020）を除去する。
  String _removeSpaces(String input) {
    return input.replaceAll('\u3000', '').replaceAll('\u0020', '');
  }

  /// 全角数字（U+FF10〜U+FF19）を半角数字（U+0030〜U+0039）に変換する。
  String _convertFullWidthDigits(String input) {
    final buffer = StringBuffer();
    for (final codeUnit in input.runes) {
      if (codeUnit >= 0xFF10 && codeUnit <= 0xFF19) {
        // 全角数字を半角数字に変換（オフセット: 0xFF10 - 0x0030 = 0xFEE0）
        buffer.writeCharCode(codeUnit - 0xFEE0);
      } else {
        buffer.writeCharCode(codeUnit);
      }
    }
    return buffer.toString();
  }

  /// 漢数字（一〜十）を半角数字（1〜10）に変換する。
  ///
  /// Nominatimの逆ジオコーディング結果が「二番町四丁目」のように
  /// 漢数字で返す場合に対応するため、町名内の漢数字を半角に変換する。
  /// 対応範囲: 一(1)〜九(9)および十(10)の単純な変換のみ。
  /// 「二十一」のような複合漢数字は変換しない（松山市の町名では不要）。
  String _convertKanjiDigits(String input) {
    const kanjiMap = {
      '一': '1',
      '二': '2',
      '三': '3',
      '四': '4',
      '五': '5',
      '六': '6',
      '七': '7',
      '八': '8',
      '九': '9',
      '十': '10',
    };
    var result = input;
    for (final entry in kanjiMap.entries) {
      result = result.replaceAll(entry.key, entry.value);
    }
    return result;
  }
}
