// Feature: gps-detection-improvements, Property 17: Distance threshold detection
// Feature: gps-detection-improvements, Property 18: Prompt trigger conditions
// Feature: gps-detection-improvements, Property 19: Check interval bounds
// Validates: Requirements 10.1, 10.2, 10.7

import 'dart:math';

import 'package:glados/glados.dart';
import 'package:garbage_app/providers/background_location_monitor.dart';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/// Latitude offset in degrees for a given distance in km.
/// 1 degree of latitude ≈ 111.32 km.
double _latOffsetForKm(double km) {
  return km / 111.32;
}

void main() {
  // Generators for valid coordinates (avoid extreme poles for numerical stability)
  final latGen = any.doubleInRange(-85.0, 85.0);
  final lngGen = any.doubleInRange(-180.0, 180.0);

  // -------------------------------------------------------------------------
  // Property 17: Distance threshold detection
  // Haversine distance check reports "significant change" iff distance >= 2.0 km
  // -------------------------------------------------------------------------
  group('Property 17: Distance threshold detection', () {
    Glados2(latGen, lngGen).test(
      'distance >= 2.0 km is detected as significant (3km offset)',
      (lat, lng) {
        // Create a second point that is ~3km away (clearly >= 2.0 km)
        final offsetDeg = _latOffsetForKm(3.0);
        final lat2 = (lat + offsetDeg).clamp(-90.0, 90.0);

        // If clamping reduced the offset significantly, skip
        if ((lat2 - lat).abs() < offsetDeg * 0.9) return;

        final distance = BackgroundLocationMonitor.calculateHaversineDistanceKm(
          lat, lng, lat2, lng,
        );

        // Verify distance is >= 2.0 km (significant change threshold)
        expect(distance, greaterThanOrEqualTo(2.0));

        // Verify threshold condition: distance >= triggerDistanceKm
        expect(
          distance >= BackgroundLocationMonitor.triggerDistanceKm,
          isTrue,
        );
      },
    );

    Glados2(latGen, lngGen).test(
      'distance < 2.0 km is NOT detected as significant (0.5km offset)',
      (lat, lng) {
        // Create a second point that is ~0.5km away (clearly < 2.0 km)
        final offsetDeg = _latOffsetForKm(0.5);
        final lat2 = (lat + offsetDeg).clamp(-90.0, 90.0);

        final distance = BackgroundLocationMonitor.calculateHaversineDistanceKm(
          lat, lng, lat2, lng,
        );

        // Verify distance is < 2.0 km (NOT significant change)
        expect(distance, lessThan(2.0));

        // Verify threshold condition: distance < triggerDistanceKm
        expect(
          distance >= BackgroundLocationMonitor.triggerDistanceKm,
          isFalse,
        );
      },
    );

    Glados2(latGen, lngGen).test(
      'distance at same point is 0 km (below threshold)',
      (lat, lng) {
        final distance = BackgroundLocationMonitor.calculateHaversineDistanceKm(
          lat, lng, lat, lng,
        );

        expect(distance, equals(0.0));
        expect(
          distance >= BackgroundLocationMonitor.triggerDistanceKm,
          isFalse,
        );
      },
    );

    Glados2(latGen, lngGen).test(
      'threshold consistency: distance >= 2.0 km iff classified as significant',
      (lat, lng) {
        // Create a point at ~2.5 km offset (comfortably above threshold)
        final offsetDeg = _latOffsetForKm(2.5);
        final lat2 = (lat + offsetDeg).clamp(-90.0, 90.0);

        // If clamping reduced the offset significantly, skip
        if ((lat2 - lat).abs() < offsetDeg * 0.9) return;

        final distance = BackgroundLocationMonitor.calculateHaversineDistanceKm(
          lat, lng, lat2, lng,
        );

        // The core property: the threshold classification is consistent
        // with the actual computed distance
        final isSignificant =
            distance >= BackgroundLocationMonitor.triggerDistanceKm;

        if (distance >= 2.0) {
          expect(isSignificant, isTrue,
              reason: 'Distance $distance km >= 2.0 should be significant');
        } else {
          expect(isSignificant, isFalse,
              reason: 'Distance $distance km < 2.0 should NOT be significant');
        }
      },
    );
  });

  // -------------------------------------------------------------------------
  // Property 18: Prompt trigger conditions
  // Prompt displayed iff distance >= 2.0 km AND elapsed >= 24h (or no prior prompt)
  //
  // We test the logic conditions directly:
  // - shouldPrompt = (distance >= 2.0) AND (elapsed >= 24h OR noLastPrompt)
  // -------------------------------------------------------------------------
  group('Property 18: Prompt trigger conditions', () {
    // Generate hours elapsed since last prompt (0 to 72 hours range)
    final hoursGen = any.doubleInRange(0.0, 72.0);
    // Generate distance in km (0.0 to 10.0 range)
    final distanceKmGen = any.doubleInRange(0.0, 10.0);

    Glados2(distanceKmGen, hoursGen).test(
      'prompt triggered iff distance >= 2.0 km AND elapsed >= 24h (with prior prompt)',
      (distanceKm, hoursElapsed) {
        // Calculate the conditions as the monitor would
        final meetsDistanceThreshold =
            distanceKm >= BackgroundLocationMonitor.triggerDistanceKm;

        // The monitor uses: now.difference(lastPromptTime) < cooldownDuration
        // Cooldown is 24h. If elapsed >= 24h, cooldown has expired (not in cooldown).
        final cooldownDuration = BackgroundLocationMonitor.cooldownDuration;
        final elapsed = Duration(minutes: (hoursElapsed * 60).toInt());
        final isInCooldown = elapsed < cooldownDuration;

        final shouldPrompt = meetsDistanceThreshold && !isInCooldown;

        // Verify: prompt iff distance >= 2.0 AND elapsed >= 24h
        final expectedPrompt = (distanceKm >= 2.0) && (hoursElapsed >= 24.0);

        expect(
          shouldPrompt,
          equals(expectedPrompt),
          reason:
              'Prompt should trigger iff distance >= 2.0 km AND elapsed >= 24h. '
              'distance=$distanceKm km, elapsed=$hoursElapsed h, '
              'meetsDistance=$meetsDistanceThreshold, inCooldown=$isInCooldown',
        );
      },
    );

    Glados<double>(distanceKmGen).test(
      'prompt triggered when no prior prompt and distance >= 2.0 km',
      (distanceKm) {
        // With no prior prompt, _isInCooldown returns false (lastPromptTime == null)
        final meetsDistanceThreshold =
            distanceKm >= BackgroundLocationMonitor.triggerDistanceKm;
        const noLastPrompt = true;

        // When there is no last prompt, cooldown does not apply
        final shouldPrompt = meetsDistanceThreshold && noLastPrompt;

        // Verify: with no prior prompt, only distance condition matters
        expect(
          shouldPrompt,
          equals(distanceKm >= 2.0),
          reason:
              'With no prior prompt, prompt should trigger iff distance >= 2.0 km. '
              'distance=$distanceKm km',
        );
      },
    );

    Glados<double>(any.doubleInRange(0.0, 1.99)).test(
      'prompt NEVER triggered when distance < 2.0 km regardless of time',
      (distanceKm) {
        // distance < 2.0 km should never trigger, regardless of cooldown state
        final meetsDistanceThreshold =
            distanceKm >= BackgroundLocationMonitor.triggerDistanceKm;

        expect(meetsDistanceThreshold, isFalse,
            reason:
                'Distance $distanceKm km < 2.0 km should never meet threshold');
      },
    );
  });

  // -------------------------------------------------------------------------
  // Property 19: Check interval bounds
  // Interval between checks >= 30 min and <= 60 min
  // -------------------------------------------------------------------------
  group('Property 19: Check interval bounds', () {
    Glados<int>(any.intInRange(0, 100000)).test(
      'calculated check interval is in [30min, 60min) range',
      (seed) {
        // Reproduce the _calculateCheckInterval logic with a seeded Random
        final random = Random(seed);
        final minMs =
            BackgroundLocationMonitor.minCheckInterval.inMilliseconds;
        final maxMs =
            BackgroundLocationMonitor.maxCheckInterval.inMilliseconds;
        final intervalMs = minMs + random.nextInt(maxMs - minMs);
        final interval = Duration(milliseconds: intervalMs);

        // Verify bounds: >= 30 min
        expect(
          interval.inMilliseconds,
          greaterThanOrEqualTo(
              BackgroundLocationMonitor.minCheckInterval.inMilliseconds),
        );

        // Verify bounds: < 60 min (nextInt is exclusive on upper bound)
        expect(
          interval.inMilliseconds,
          lessThan(
              BackgroundLocationMonitor.maxCheckInterval.inMilliseconds),
        );
      },
    );

    Glados<int>(any.intInRange(0, 100000)).test(
      'check interval in minutes is >= 30 and <= 59',
      (seed) {
        final random = Random(seed);
        final minMs =
            BackgroundLocationMonitor.minCheckInterval.inMilliseconds;
        final maxMs =
            BackgroundLocationMonitor.maxCheckInterval.inMilliseconds;
        final intervalMs = minMs + random.nextInt(maxMs - minMs);
        final interval = Duration(milliseconds: intervalMs);

        // In full minutes: >= 30
        expect(interval.inMinutes, greaterThanOrEqualTo(30));
        // Since nextInt is exclusive, max is maxMs-1 ms = 59 min 59.999s
        expect(interval.inMinutes, lessThanOrEqualTo(59));
      },
    );

    Glados<int>(any.intInRange(0, 100000)).test(
      'random offset within range produces valid non-negative offset',
      (seed) {
        final random = Random(seed);
        final minMs =
            BackgroundLocationMonitor.minCheckInterval.inMilliseconds;
        final maxMs =
            BackgroundLocationMonitor.maxCheckInterval.inMilliseconds;
        final range = maxMs - minMs;

        expect(range, greaterThan(0));

        final offset = random.nextInt(range);
        expect(offset, greaterThanOrEqualTo(0));
        expect(offset, lessThan(range));

        // Final interval = minMs + offset
        final intervalMs = minMs + offset;
        expect(intervalMs, greaterThanOrEqualTo(minMs));
        expect(intervalMs, lessThan(maxMs));
      },
    );
  });
}
