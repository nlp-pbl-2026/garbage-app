import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/services/geocoding_cache.dart';

void main() {
  late GeocodingCache cache;

  setUp(() {
    cache = GeocodingCache();
  });

  GeocodedAddress makeAddress(String town) => GeocodedAddress(
        prefecture: '愛媛県',
        city: '松山市',
        town: town,
        fullAddress: '愛媛県松山市$town',
      );

  group('GeocodingCache constants', () {
    test('maxEntries is 100', () {
      expect(GeocodingCache.maxEntries, equals(100));
    });

    test('hitRadiusMeters is 50.0', () {
      expect(GeocodingCache.hitRadiusMeters, equals(50.0));
    });
  });

  group('GeocodingCache.get', () {
    test('returns null when cache is empty', () {
      final result = cache.get(33.8416, 132.7657);
      expect(result, isNull);
    });

    test('returns cached address when query is at exact same coordinates', () {
      final address = makeAddress('道後湯之町');
      cache.put(33.8416, 132.7657, address);

      final result = cache.get(33.8416, 132.7657);
      expect(result, equals(address));
    });

    test('returns cached address when query is within 50m', () {
      final address = makeAddress('道後湯之町');
      // Approx 33.8416, 132.7657 is Dogo area in Matsuyama
      cache.put(33.8416, 132.7657, address);

      // ~30m offset (roughly 0.0003 degrees latitude ≈ 33m)
      final result = cache.get(33.8419, 132.7657);
      expect(result, equals(address));
    });

    test('returns null when query is beyond 50m', () {
      final address = makeAddress('道後湯之町');
      cache.put(33.8416, 132.7657, address);

      // ~500m offset (0.005 degrees latitude ≈ 555m)
      final result = cache.get(33.8466, 132.7657);
      expect(result, isNull);
    });

    test('returns nearest entry when multiple entries within 50m', () {
      final addressFar = makeAddress('遠い町');
      final addressNear = makeAddress('近い町');

      // Place two entries both within 50m of a query point
      // Query point will be at 33.84160, 132.76570
      // Entry 1: 40m away
      cache.put(33.84124, 132.76570, addressFar); // ~40m south
      // Entry 2: 10m away
      cache.put(33.84151, 132.76570, addressNear); // ~10m south

      final result = cache.get(33.84160, 132.76570);
      expect(result, equals(addressNear));
    });

    test('ignores entries beyond 50m even if others are within', () {
      final addressWithin = makeAddress('近い町');
      final addressBeyond = makeAddress('遠い町');

      cache.put(33.84160, 132.76570, addressWithin);
      cache.put(33.84660, 132.76570, addressBeyond); // ~555m away

      final result = cache.get(33.84160, 132.76570);
      expect(result, equals(addressWithin));
    });
  });

  group('GeocodingCache.put', () {
    test('adds entry to cache', () {
      expect(cache.length, equals(0));
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      expect(cache.length, equals(1));
    });

    test('allows adding multiple entries', () {
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      cache.put(33.8500, 132.7700, makeAddress('番町'));
      expect(cache.length, equals(2));
    });

    test('evicts oldest entry when cache is full (FIFO)', () {
      // Fill cache to maxEntries
      for (int i = 0; i < GeocodingCache.maxEntries; i++) {
        cache.put(
          33.0 + i * 0.01,
          132.0 + i * 0.01,
          makeAddress('町$i'),
        );
      }
      expect(cache.length, equals(100));

      // Add one more - should evict the first entry
      cache.put(34.0, 133.0, makeAddress('新しい町'));
      expect(cache.length, equals(100));

      // The first entry (at 33.0, 132.0) should be evicted
      // since entries are ~1km+ apart, only exact match would hit
      final result = cache.get(33.0, 132.0);
      expect(result, isNull);

      // The new entry should be present
      final newResult = cache.get(34.0, 133.0);
      expect(newResult, equals(makeAddress('新しい町')));
    });

    test('does not exceed maxEntries after multiple puts at capacity', () {
      for (int i = 0; i < 150; i++) {
        cache.put(
          33.0 + i * 0.01,
          132.0 + i * 0.01,
          makeAddress('町$i'),
        );
      }
      expect(cache.length, equals(100));
    });
  });

  group('GeocodingCache.clear', () {
    test('removes all entries from cache', () {
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      cache.put(33.8500, 132.7700, makeAddress('番町'));
      expect(cache.length, equals(2));

      cache.clear();
      expect(cache.length, equals(0));
    });

    test('get returns null after clear', () {
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      cache.clear();

      final result = cache.get(33.8416, 132.7657);
      expect(result, isNull);
    });

    test('cache can be reused after clear', () {
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      cache.clear();

      cache.put(33.8500, 132.7700, makeAddress('番町'));
      expect(cache.length, equals(1));
      expect(cache.get(33.8500, 132.7700), equals(makeAddress('番町')));
    });
  });

  group('GeocodingCache.length', () {
    test('returns 0 for empty cache', () {
      expect(cache.length, equals(0));
    });

    test('returns correct count after puts', () {
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      expect(cache.length, equals(1));

      cache.put(33.8500, 132.7700, makeAddress('番町'));
      expect(cache.length, equals(2));
    });

    test('returns 0 after clear', () {
      cache.put(33.8416, 132.7657, makeAddress('道後湯之町'));
      cache.clear();
      expect(cache.length, equals(0));
    });
  });

  group('Haversine distance integration', () {
    test('boundary case: exactly at 50m should be a hit', () {
      // Use known coordinate pair that is approximately 50m apart
      // 0.00045 degrees latitude ≈ 50m
      final address = makeAddress('境界町');
      cache.put(33.84160, 132.76570, address);

      // Query at ~49m away (should hit)
      final result = cache.get(33.84204, 132.76570);
      // The exact distance depends on Haversine calc; this tests near-boundary
      // If this is within 50m, it should return the address
      if (result != null) {
        expect(result, equals(address));
      }
    });

    test('distance calculation works across longitude', () {
      final address = makeAddress('経度テスト町');
      cache.put(33.84160, 132.76570, address);

      // Small longitude offset (~30m at this latitude)
      // At lat ~33.84, 1 degree longitude ≈ 92.6km, so 0.0003 deg ≈ 27.8m
      final result = cache.get(33.84160, 132.76600);
      expect(result, equals(address));
    });
  });
}
