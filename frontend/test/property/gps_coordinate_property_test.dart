// Feature: gps-detection-improvements, Property 10: GPS accuracy validation
// Validates: Requirements 8.1

import 'package:glados/glados.dart';
import 'package:garbage_app/models/gps_detection.dart';

void main() {
  group('Property 10: GPS accuracy validation', () {
    Glados<double>(any.doubleInRange(0.0, 10000.0)).test(
      'isAccurate returns true if and only if accuracy <= 500.0',
      (accuracy) {
        final coord = GpsCoordinate(
          latitude: 0,
          longitude: 0,
          accuracy: accuracy,
        );
        expect(coord.isAccurate, equals(accuracy <= 500.0));
      },
    );
  });
}
