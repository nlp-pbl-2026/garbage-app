// Temporary file to check glados API
@TestOn('vm')
import 'package:test/test.dart';
import 'package:glados/glados.dart';

void main() {
  // Test with Glados2<int, int> for two integers
  Glados2<int, int>().test('check int pair works', (a, b) {
    expect(a is int, isTrue);
    expect(b is int, isTrue);
  });
}
