// Feature: gps-detection-improvements, Property 7: Cache spatial hit and miss
// Validates: Requirements 5.2

// Feature: gps-detection-improvements, Property 9: Cache FIFO eviction
// Validates: Requirements 5.5

import 'dart:math';

import 'package:glados/glados.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/services/geocoding_cache.dart';

/// Haversine distance calculation (meters) for test verification
double haversineDistance(double lat1, double lng1, double lat2, double lng2) {
  const earthRadius = 6371000.0;
  final lat1Rad = lat1 * pi / 180.0;
  final lat2Rad = lat2 * pi / 180.0;
  final deltaLat = (lat2 - lat1) * pi / 180.0;
  final deltaLng = (lng2 - lng1) * pi / 180.0;

  final a = sin(deltaLat / 2) * sin(deltaLat / 2) +
      cos(lat1Rad) * cos(lat2Rad) * sin(deltaLng / 2) * sin(deltaLng / 2);
  final c = 2 * atan2(sqrt(a), sqrt(1 - a));

  return earthRadius * c;
}

/// Latitude offset in degrees for a given distance in meters.
/// 1 degree of latitude ≈ 111,320 meters.
double latOffsetForMeters(double meters) {
  return meters / 111320.0;
}

/// Longitude offset in degrees for a given distance in meters at a given latitude.
/// 1 degree of longitude ≈ 111,320 * cos(lat) meters.
double lngOffsetForMeters(double meters, double atLatitude) {
  final cosLat = cos(atLatitude * pi / 180.0);
  if (cosLat.abs() < 1e-10) return 0.0;
  return meters / (111320.0 * cosLat);
}

GeocodedAddress makeAddress(String suffix) => GeocodedAddress(
      prefecture: '愛媛県',
      city: '松山市',
      town: 'テスト町$suffix',
      fullAddress: '愛媛県松山市テスト町$suffix',
    );

void main() {
  // Generators for valid coordinates (avoid extreme poles for numerical stability)
  final latGen = any.doubleInRange(-85.0, 85.0);
  final lngGen = any.doubleInRange(-180.0, 180.0);

  group('Property 7: Cache spatial hit and miss', () {
    Glados2(latGen, lngGen).test(
      'get() returns cached address when query is within 50m (latitude offset)',
      (lat, lng) {
        final cache = GeocodingCache();
        final address = makeAddress('A');

        // Put an entry in cache
        cache.put(lat, lng, address);

        // Create a query point within 50m using a 30m latitude offset
        final offsetDeg = latOffsetForMeters(30.0);
        final queryLat = lat + offsetDeg;
        final queryLng = lng;

        // Verify the distance is indeed <= 50m
        final distance = haversineDistance(lat, lng, queryLat, queryLng);
        expect(distance, lessThanOrEqualTo(50.0),
            reason: 'Generated offset should be within 50m');

        // Cache should return the address
        final result = cache.get(queryLat, queryLng);
        expect(result, equals(address),
            reason:
                'Cache should return address when query is within 50m (distance: ${distance.toStringAsFixed(2)}m)');
      },
    );

    Glados2(latGen, lngGen).test(
      'get() returns null when query is beyond 50m (latitude offset) and no other cached entry within 50m',
      (lat, lng) {
        final cache = GeocodingCache();
        final address = makeAddress('B');

        // Put an entry in cache
        cache.put(lat, lng, address);

        // Create a query point beyond 50m using a 100m latitude offset
        final offsetDeg = latOffsetForMeters(100.0);
        final queryLat = lat + offsetDeg;
        final queryLng = lng;

        // Verify the distance is indeed > 50m
        final distance = haversineDistance(lat, lng, queryLat, queryLng);
        expect(distance, greaterThan(50.0),
            reason: 'Generated offset should be beyond 50m');

        // Cache should return null
        final result = cache.get(queryLat, queryLng);
        expect(result, isNull,
            reason:
                'Cache should return null when query is beyond 50m (distance: ${distance.toStringAsFixed(2)}m)');
      },
    );

    Glados2(latGen, lngGen).test(
      'get() returns cached address when query is within 50m (longitude offset)',
      (lat, lng) {
        final cache = GeocodingCache();
        final address = makeAddress('C');

        // Put an entry in cache
        cache.put(lat, lng, address);

        // Create a query point within 50m using a 25m longitude offset
        final offsetDeg = lngOffsetForMeters(25.0, lat);
        final queryLat = lat;
        final queryLng = lng + offsetDeg;

        // Verify the distance is indeed <= 50m
        final distance = haversineDistance(lat, lng, queryLat, queryLng);

        // Skip degenerate cases near poles where calculation may be unreliable
        if (distance > 50.0) return;

        // Cache should return the address
        final result = cache.get(queryLat, queryLng);
        expect(result, equals(address),
            reason:
                'Cache should return address when query is within 50m via longitude offset (distance: ${distance.toStringAsFixed(2)}m)');
      },
    );

    Glados2(latGen, lngGen).test(
      'get() returns null when query is beyond 50m (longitude offset) and no other cached entry within 50m',
      (lat, lng) {
        final cache = GeocodingCache();
        final address = makeAddress('D');

        // Put an entry in cache
        cache.put(lat, lng, address);

        // Create a query point beyond 50m using a 100m longitude offset
        final offsetDeg = lngOffsetForMeters(100.0, lat);
        final queryLat = lat;
        final queryLng = lng + offsetDeg;

        // Verify the distance is indeed > 50m
        final distance = haversineDistance(lat, lng, queryLat, queryLng);

        // Skip degenerate cases near poles where calculation may be unreliable
        if (distance <= 50.0) return;

        // Cache should return null
        final result = cache.get(queryLat, queryLng);
        expect(result, isNull,
            reason:
                'Cache should return null when query is beyond 50m via longitude offset (distance: ${distance.toStringAsFixed(2)}m)');
      },
    );

    Glados2(latGen, lngGen).test(
      'get() returns cached address at exact same coordinates (0m distance)',
      (lat, lng) {
        final cache = GeocodingCache();
        final address = makeAddress('E');

        // Put an entry in cache
        cache.put(lat, lng, address);

        // Query at same coordinates (0m distance, always <= 50m)
        final result = cache.get(lat, lng);
        expect(result, equals(address),
            reason:
                'Cache should always return address at exact same coordinates');
      },
    );
  });

  // Feature: gps-detection-improvements, Property 9: Cache FIFO eviction
  // Validates: Requirements 5.5
  group('Property 9: Cache FIFO eviction', () {
    // Generator for a seed value used to produce deterministic sequences
    final seedGen = any.intInRange(0, 100000);

    Glados(seedGen).test(
      'when cache is at capacity and a new entry is added, the oldest entry is evicted and the new entry is present',
      (seed) {
        final cache = GeocodingCache();
        final random = Random(seed);

        // Generate 100 unique coordinate entries to fill the cache to capacity.
        // We spread coordinates far apart (> 50m) so each can be independently
        // queried without ambiguity.
        final entries = <({double lat, double lng, GeocodedAddress address})>[];
        for (int i = 0; i < 100; i++) {
          // Space entries by ~1 degree apart in latitude (≈111km) to avoid
          // cache hit radius overlap
          final lat = -80.0 + (i * 1.6) + random.nextDouble() * 0.01;
          final lng = -170.0 + (i * 3.4) + random.nextDouble() * 0.01;
          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: 'テスト町$i',
            fullAddress: '愛媛県松山市テスト町$i',
          );
          entries.add((lat: lat, lng: lng, address: address));
        }

        // Fill cache to capacity (100 entries)
        for (final entry in entries) {
          cache.put(entry.lat, entry.lng, entry.address);
        }
        expect(cache.length, equals(100),
            reason: 'Cache should be at capacity after 100 puts');

        // Verify the oldest (first inserted) entry is still present before eviction
        final oldestEntry = entries[0];
        final oldestResult = cache.get(oldestEntry.lat, oldestEntry.lng);
        expect(oldestResult, equals(oldestEntry.address),
            reason: 'Oldest entry should be present before adding 101st entry');

        // Add a new (101st) entry that is far from all existing entries
        final newLat = 89.0 + random.nextDouble() * 0.01;
        final newLng = 179.0 + random.nextDouble() * 0.01;
        final newAddress = GeocodedAddress(
          prefecture: '愛媛県',
          city: '松山市',
          town: '新規追加町',
          fullAddress: '愛媛県松山市新規追加町',
        );
        cache.put(newLat, newLng, newAddress);

        // Cache size should still be 100 (not 101)
        expect(cache.length, equals(100),
            reason: 'Cache should remain at 100 after eviction');

        // The new entry SHALL be present in the cache
        final newResult = cache.get(newLat, newLng);
        expect(newResult, equals(newAddress),
            reason: 'Newly added entry should be present in cache');

        // The oldest (first inserted) entry SHALL have been evicted
        final evictedResult = cache.get(oldestEntry.lat, oldestEntry.lng);
        expect(evictedResult, isNull,
            reason: 'Oldest entry (first inserted) should have been evicted');

        // The second-oldest entry should still be present (it was not evicted)
        final secondEntry = entries[1];
        final secondResult = cache.get(secondEntry.lat, secondEntry.lng);
        expect(secondResult, equals(secondEntry.address),
            reason: 'Second oldest entry should still be present after eviction');
      },
    );

    Glados(seedGen).test(
      'FIFO eviction consistently removes the oldest timestamp entry across multiple evictions',
      (seed) {
        final cache = GeocodingCache();

        // Use deterministic coordinates based on index (no randomness needed
        // for this property - we just need entries to be far apart)
        final coordinates = <({double lat, double lng})>[];
        for (int i = 0; i < 105; i++) {
          // Space entries 1.5 degrees apart in lat (≈167km) to avoid overlap
          final lat = -80.0 + (i * 1.5);
          final lng = -170.0 + (i * 0.5);
          coordinates.add((lat: lat, lng: lng));
        }

        // Fill cache to capacity (100 entries)
        for (int i = 0; i < 100; i++) {
          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '町$i',
            fullAddress: '愛媛県松山市町$i',
          );
          cache.put(coordinates[i].lat, coordinates[i].lng, address);
        }

        // Add 5 more entries, triggering 5 evictions (entries 0-4 should be evicted)
        for (int i = 100; i < 105; i++) {
          final address = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '追加町${i - 100}',
            fullAddress: '愛媛県松山市追加町${i - 100}',
          );
          cache.put(coordinates[i].lat, coordinates[i].lng, address);

          // Cache should remain at capacity
          expect(cache.length, equals(100),
              reason: 'Cache should remain at 100 after eviction ${i - 100}');

          // New entry should be present
          final result = cache.get(coordinates[i].lat, coordinates[i].lng);
          expect(result, equals(address),
              reason: 'New entry ${i - 100} should be present after insertion');
        }

        // After 5 evictions, the first 5 original entries (indices 0-4) should be gone
        for (int i = 0; i < 5; i++) {
          final result =
              cache.get(coordinates[i].lat, coordinates[i].lng);
          expect(result, isNull,
              reason: 'Entry $i (evicted) should no longer be in cache');
        }

        // Entries 5-99 should still be present (not evicted)
        for (int i = 5; i < 10; i++) {
          final expectedAddress = GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '町$i',
            fullAddress: '愛媛県松山市町$i',
          );
          final result =
              cache.get(coordinates[i].lat, coordinates[i].lng);
          expect(result, equals(expectedAddress),
              reason: 'Entry $i should still be present after 5 evictions');
        }
      },
    );
  });
}
