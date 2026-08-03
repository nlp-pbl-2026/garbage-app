import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/services/abstract_district_matcher.dart';
import 'package:garbage_app/services/abstract_location_service.dart';
import 'package:garbage_app/services/abstract_reverse_geocoder.dart';
import 'package:garbage_app/services/geocoding_cache.dart';
import 'package:garbage_app/services/geojson_resolver.dart';

/// テスト用のモックLocationService
///
/// [getCurrentPositionBehavior] を設定して各テストでの振る舞いを制御する。
class MockLocationService implements AbstractLocationService {
  /// getCurrentPosition() 呼び出し時の振る舞い
  Future<GpsCoordinate> Function()? getCurrentPositionBehavior;

  @override
  Future<LocationPermissionStatus> checkPermission() async {
    return LocationPermissionStatus.granted;
  }

  @override
  Future<LocationPermissionStatus> requestPermission() async {
    return LocationPermissionStatus.granted;
  }

  @override
  Future<bool> isLocationServiceEnabled() async {
    return true;
  }

  @override
  Future<GpsCoordinate> getCurrentPosition() async {
    if (getCurrentPositionBehavior != null) {
      return getCurrentPositionBehavior!();
    }
    return const GpsCoordinate(
      latitude: 33.8416,
      longitude: 132.7657,
      accuracy: 10.0,
    );
  }
}

/// テスト用のモックReverseGeocoder
class MockReverseGeocoder implements AbstractReverseGeocoder {
  @override
  Future<GeocodedAddress> getAddressFromCoordinates(
    double latitude,
    double longitude,
  ) async {
    return const GeocodedAddress(
      prefecture: '愛媛県',
      city: '松山市',
      town: '道後湯之町',
      fullAddress: '愛媛県松山市道後湯之町',
    );
  }
}

/// テスト用のモックDistrictMatcher
class MockDistrictMatcher implements AbstractDistrictMatcher {
  @override
  Future<void> loadChoumeiData() async {}

  @override
  DistrictMatchResult matchDistrict(GeocodedAddress address, {String? areaId}) {
    return const DistrictMatchResult(
      districtNumber: 3,
      districtName: '道後',
      matchedTown: '道後湯之町',
    );
  }

  @override
  List<DistrictCandidate> matchDistrictCandidates(
    GeocodedAddress address, {
    String? areaId,
  }) {
    return const [
      DistrictCandidate(
        districtNumber: 3,
        districtName: '道後',
        townName: '道後湯之町',
      ),
    ];
  }
}

/// テスト用のモックGeoJsonResolver
///
/// isLoaded を false にしてGeoJSON判定をスキップさせる。
class MockGeoJsonResolver implements GeoJsonResolver {
  @override
  bool get isLoaded => false;

  @override
  Future<void> loadPolygons() async {}

  @override
  DistrictMatchResult? resolveDistrict(double latitude, double longitude) {
    return null;
  }
}

/// テスト用のモックGeocodingCache
class MockGeocodingCache implements GeocodingCache {
  @override
  GeocodedAddress? get(double latitude, double longitude) => null;

  @override
  void put(double latitude, double longitude, GeocodedAddress address) {}

  @override
  void clear() {}

  @override
  int get length => 0;
}
