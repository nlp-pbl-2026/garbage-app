import '../models/gps_detection.dart';
import 'abstract_district_matcher.dart';
import 'address_normalizer.dart';
import 'municipality_data_service.dart';

/// Matches only towns in Matsuyama's official collection-area address table.
/// GPS coordinates and the placeholder GeoJSON are never treated as boundaries.
class OfficialCollectionMatcher implements AbstractDistrictMatcher {
  OfficialCollectionMatcher({MunicipalityDataService? data})
      : _data = data ?? MunicipalityDataService();
  final MunicipalityDataService _data;
  List<Map<String, dynamic>>? _entries;
  Map<String, String>? _names;

  @override
  Future<void> loadChoumeiData() async {
    _entries ??= ((await _data.addresses)['entries'] as List).cast<Map<String, dynamic>>();
    _names ??= {for (final area in await _data.getAreas()) area['id'] as String: area['name'] as String};
  }

  List<DistrictCandidate> _candidates(GeocodedAddress address) {
    if (address.city != '松山市' || address.prefecture != '愛媛県') throw OutOfAreaException();
    if (_entries == null || _names == null) throw StateError('Address table is not loaded');
    final normalize = AddressNormalizer().normalize;
    final town = normalize(address.town);
    final matches = _entries!.where((entry) =>
      normalize(entry['town'] as String) == town ||
      normalize(entry['lookup_town'] as String) == town).toList();
    final unique = <String, DistrictCandidate>{};
    for (final entry in matches) {
      final id = entry['area_id'] as String;
      unique[id] = DistrictCandidate(
        districtNumber: int.tryParse(id.split('-').last) ?? 0,
        districtName: _names![id] ?? id,
        townName: entry['town'] as String,
        collectionAreaId: id,
      );
    }
    return unique.values.toList();
  }

  @override
  DistrictMatchResult matchDistrict(GeocodedAddress address, {String? areaId}) {
    final matches = _candidates(address);
    if (matches.length != 1) throw DistrictNotFoundException();
    final candidate = matches.single;
    return DistrictMatchResult(
      districtNumber: candidate.districtNumber,
      districtName: candidate.districtName,
      matchedTown: candidate.townName,
      collectionAreaId: candidate.collectionAreaId,
    );
  }

  @override
  List<DistrictCandidate> matchDistrictCandidates(GeocodedAddress address, {String? areaId}) => _candidates(address);
}
