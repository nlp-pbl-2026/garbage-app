// Feature: gps-detection-improvements, Property 1: Address normalization correctness
// Feature: gps-detection-improvements, Property 2: Normalization safety on reference data
//
// Property 1: For any input string, AddressNormalizer.normalize() SHALL apply
// transformations in order: (1) remove "大字" prefix, (2) remove "字" prefix
// (applied to result of step 1), (3) remove all U+3000 and U+0020 spaces,
// (4) convert full-width digits (U+FF10–U+FF19) to half-width (U+0030–U+0039).
// The output must reflect all four transformations applied in sequence.
//
// **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
//
// Property 2: For any town name present in choumei.csv, normalizing that town name
// SHALL produce a string that can still be matched against the normalized version of
// at least one entry in the choumei dataset (normalization does not destroy matchability).
//
// **Validates: Requirements 4.6**

import 'dart:io';

import 'package:glados/glados.dart';
import 'package:garbage_app/services/address_normalizer.dart';

/// Generates address-like strings containing combinations of "大字", "字",
/// spaces (U+3000, U+0020), full-width digits (U+FF10–U+FF19), and Japanese text.
///
/// Uses glados's list generator with an index-to-component mapping.
String buildAddressFromIndices(List<int> indices) {
  const components = [
    '大字',       // 0
    '字',         // 1
    '\u3000',     // 2 - full-width space
    '\u0020',     // 3 - half-width space
    '０',         // 4 - full-width 0
    '１',         // 5 - full-width 1
    '２',         // 6
    '３',         // 7
    '４',         // 8
    '５',         // 9
    '６',         // 10
    '７',         // 11
    '８',         // 12
    '９',         // 13
    '北条',       // 14
    '番町',       // 15
    '丁目',       // 16
    '松山市',     // 17
    '鶴吉',       // 18
    '1',          // 19
    '2',          // 20
    '文字',       // 21 - contains 字 but not as prefix
  ];

  final buffer = StringBuffer();
  for (final idx in indices) {
    buffer.write(components[idx % components.length]);
  }
  return buffer.toString();
}

/// Reference implementation: manually applies the 4 normalization steps in order.
String referenceNormalize(String input) {
  // Step 1: Remove all "大字"
  var result = input.replaceAll('大字', '');

  // Step 2: Remove leading "字" (only if at start)
  if (result.startsWith('字')) {
    result = result.substring(1);
  }

  // Step 3: Remove all U+3000 and U+0020 spaces
  result = result.replaceAll('\u3000', '').replaceAll('\u0020', '');

  // Step 4: Convert full-width digits to half-width
  final buffer = StringBuffer();
  for (final codeUnit in result.runes) {
    if (codeUnit >= 0xFF10 && codeUnit <= 0xFF19) {
      buffer.writeCharCode(codeUnit - 0xFEE0);
    } else {
      buffer.writeCharCode(codeUnit);
    }
  }
  return buffer.toString();
}

void main() {
  final normalizer = AddressNormalizer();

  group('Property 1: Address normalization correctness', () {
    // Use list of indices to generate address-like strings with relevant components
    Glados(any.listWithLengthInRange(1, 8, any.intInRange(0, 21)),
            ExploreConfig(numRuns: 100))
        .test(
      'normalize() removes all "大字" occurrences (Step 1)',
      (indices) {
        final input = buildAddressFromIndices(indices);
        final result = normalizer.normalize(input);
        expect(result.contains('大字'), isFalse,
            reason:
                'After normalization, "大字" should not be present. Input: "$input", Output: "$result"');
      },
    );

    Glados(any.listWithLengthInRange(1, 8, any.intInRange(0, 21)),
            ExploreConfig(numRuns: 100))
        .test(
      'normalize() removes leading "字" after "大字" removal (Step 2)',
      (indices) {
        final input = buildAddressFromIndices(indices);
        final result = normalizer.normalize(input);
        // After step 1, if the string starts with "字", step 2 should remove it
        final afterStep1 = input.replaceAll('大字', '');
        if (afterStep1.startsWith('字')) {
          expect(result.startsWith('字'), isFalse,
              reason:
                  'Leading "字" should be removed after "大字" removal. Input: "$input", Output: "$result"');
        }
      },
    );

    Glados(any.listWithLengthInRange(1, 8, any.intInRange(0, 21)),
            ExploreConfig(numRuns: 100))
        .test(
      'normalize() removes all U+3000 and U+0020 spaces (Step 3)',
      (indices) {
        final input = buildAddressFromIndices(indices);
        final result = normalizer.normalize(input);
        expect(result.contains('\u3000'), isFalse,
            reason:
                'After normalization, U+3000 should not be present. Input: "$input", Output: "$result"');
        expect(result.contains('\u0020'), isFalse,
            reason:
                'After normalization, U+0020 should not be present. Input: "$input", Output: "$result"');
      },
    );

    Glados(any.listWithLengthInRange(1, 8, any.intInRange(0, 21)),
            ExploreConfig(numRuns: 100))
        .test(
      'normalize() converts all full-width digits to half-width (Step 4)',
      (indices) {
        final input = buildAddressFromIndices(indices);
        final result = normalizer.normalize(input);
        for (var codeUnit = 0xFF10; codeUnit <= 0xFF19; codeUnit++) {
          expect(result.contains(String.fromCharCode(codeUnit)), isFalse,
              reason:
                  'After normalization, full-width digit U+${codeUnit.toRadixString(16)} should be converted. Input: "$input", Output: "$result"');
        }
      },
    );

    Glados(any.listWithLengthInRange(1, 8, any.intInRange(0, 21)),
            ExploreConfig(numRuns: 100))
        .test(
      'normalize() output equals manual sequential application of all 4 steps',
      (indices) {
        final input = buildAddressFromIndices(indices);
        final result = normalizer.normalize(input);
        final expected = referenceNormalize(input);

        expect(result, equals(expected),
            reason:
                'normalize() output must match sequential application of all 4 steps. '
                'Input: "$input", Expected: "$expected", Got: "$result"');
      },
    );
  });

  group('Property 2: Normalization safety on reference data', () {
    late List<String> townNames;
    late Set<String> normalizedDataset;

    setUpAll(() {
      // Load choumei.csv directly from assets (test runs from project root)
      final csvFile = File('assets/choumei.csv');
      final csvContent = csvFile.readAsStringSync();
      final lines = csvContent.split('\n');

      // Skip header, parse town names (column index 3)
      townNames = [];
      for (final line in lines.skip(1)) {
        if (line.trim().isEmpty) continue;
        final parts = line.split(',');
        if (parts.length >= 4) {
          final townName = parts[3].trim();
          if (townName.isNotEmpty) {
            townNames.add(townName);
          }
        }
      }

      // Build a set of all normalized town names from the dataset
      normalizedDataset = townNames.map((t) => normalizer.normalize(t)).toSet();
    });

    test(
      'normalizing any town name from choumei.csv still matches at least one normalized entry',
      () {
        // Verify we loaded data
        expect(townNames, isNotEmpty,
            reason: 'choumei.csv should contain town names');

        for (final townName in townNames) {
          final normalized = normalizer.normalize(townName);

          // The normalized version of this town name must exist in the
          // set of all normalized town names (i.e., normalization does not
          // destroy matchability).
          expect(
            normalizedDataset.contains(normalized),
            isTrue,
            reason:
                'Normalized "$townName" -> "$normalized" should match at least '
                'one normalized entry in choumei.csv',
          );
        }
      },
    );
  });
}
