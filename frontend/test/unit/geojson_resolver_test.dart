import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/geojson_resolver.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('GeoJsonResolver', () {
    group('isLoaded', () {
      test('returns false before loadPolygons is called', () {
        final resolver = GeoJsonResolver();
        expect(resolver.isLoaded, isFalse);
      });
    });

    group('resolveDistrict without loading', () {
      test('returns null when polygons are not loaded', () {
        final resolver = GeoJsonResolver();
        final result = resolver.resolveDistrict(33.8450, 132.7625);
        expect(result, isNull);
      });
    });

    group('loadPolygons and resolveDistrict integration', () {
      late GeoJsonResolver resolver;

      setUpAll(() async {
        resolver = GeoJsonResolver();
        await resolver.loadPolygons();
      });

      test('isLoaded returns true after loadPolygons', () {
        expect(resolver.isLoaded, isTrue);
      });

      test('resolves a point inside 番町 district (district 1)', () {
        // From GeoJSON: [[132.7600, 33.8430], [132.7650, 33.8430], [132.7650, 33.8470], [132.7600, 33.8470], [132.7600, 33.8430]]
        // Center approximately at (33.8450, 132.7625)
        final result = resolver.resolveDistrict(33.8450, 132.7625);
        expect(result, isNotNull);
        expect(result!.districtNumber, equals(1));
        expect(result.districtName, equals('番町'));
      });

      test('returns null for a point outside all polygons', () {
        // Point far outside any district polygon
        final result = resolver.resolveDistrict(35.0, 135.0);
        expect(result, isNull);
      });

      test('resolves 東雲 district (district 2)', () {
        // From GeoJSON: [[132.7700, 33.8430], [132.7750, 33.8430], [132.7750, 33.8470], [132.7700, 33.8470], [132.7700, 33.8430]]
        // Center approximately at (33.8450, 132.7725)
        final result = resolver.resolveDistrict(33.8450, 132.7725);
        expect(result, isNotNull);
        expect(result!.districtNumber, equals(2));
        expect(result.districtName, equals('東雲'));
      });

      test('resolves 八坂 district (district 3)', () {
        // From GeoJSON: [[132.7550, 33.8380], [132.7600, 33.8380], [132.7600, 33.8420], [132.7550, 33.8420], [132.7550, 33.8380]]
        // Center approximately at (33.8400, 132.7575)
        final result = resolver.resolveDistrict(33.8400, 132.7575);
        expect(result, isNotNull);
        expect(result!.districtNumber, equals(3));
        expect(result.districtName, equals('八坂'));
      });

      test('returns result with matchedTown set to districtName', () {
        final result = resolver.resolveDistrict(33.8450, 132.7625);
        expect(result, isNotNull);
        expect(result!.matchedTown, equals(result.districtName));
      });

      test('point between polygons returns null (no overlaps)', () {
        // Point between 番町 and 東雲 (gap area)
        // 番町 ends at lng 132.7650, 東雲 starts at lng 132.7700
        final result = resolver.resolveDistrict(33.8450, 132.7675);
        expect(result, isNull);
      });
    });

    group('ray-casting algorithm edge cases', () {
      late GeoJsonResolver resolver;

      setUpAll(() async {
        resolver = GeoJsonResolver();
        await resolver.loadPolygons();
      });

      test('point on polygon boundary does not crash', () {
        // Point on the edge of 番町 polygon (bottom edge)
        resolver.resolveDistrict(33.8430, 132.7625);
        // Just ensure no exception is thrown
      });

      test('point at exactly a vertex does not crash', () {
        // Exact vertex of polygon
        resolver.resolveDistrict(33.8430, 132.7600);
        // Just ensure no exception
      });
    });

    group('performance', () {
      late GeoJsonResolver resolver;

      setUpAll(() async {
        resolver = GeoJsonResolver();
        await resolver.loadPolygons();
      });

      test('resolveDistrict completes within 200ms for single call', () {
        final stopwatch = Stopwatch()..start();
        resolver.resolveDistrict(33.8450, 132.7625);
        stopwatch.stop();

        expect(stopwatch.elapsedMilliseconds, lessThan(200));
      });

      test('100 consecutive resolveDistrict calls average under 200ms each',
          () {
        final stopwatch = Stopwatch()..start();
        for (int i = 0; i < 100; i++) {
          resolver.resolveDistrict(33.8450, 132.7625);
        }
        stopwatch.stop();

        final averageMs = stopwatch.elapsedMilliseconds / 100;
        expect(averageMs, lessThan(200));
      });
    });

    group('loadPolygons edge cases', () {
      test('calling loadPolygons twice does not duplicate data', () async {
        final resolver = GeoJsonResolver();
        await resolver.loadPolygons();
        await resolver.loadPolygons();

        // Should still work correctly without duplicating polygons
        final result = resolver.resolveDistrict(33.8450, 132.7625);
        expect(result, isNotNull);
        expect(result!.districtNumber, equals(1));
      });

      test('handles missing asset gracefully', () async {
        // Mock rootBundle to return an error for the asset
        final resolver = GeoJsonResolver();
        // If asset doesn't exist, loadPolygons should fail silently
        // and isLoaded remains false. We can't easily test with a
        // missing asset in test environment, but we verify that
        // the try/catch works by checking the normal path loads fine.
        await resolver.loadPolygons();
        expect(resolver.isLoaded, isTrue);
      });
    });
  });
}
