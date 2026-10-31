import 'package:flutter/foundation.dart' show debugPrint;
import '../models/gps_detection.dart';
import '../models/region.dart';
import 'abstract_district_matcher.dart';
import 'address_normalizer.dart';
import 'municipality_data_service.dart';

/// Exact official town-table matches are candidates for user confirmation.
/// Coordinates and administrative GeoJSON never imply collection boundaries.
class OfficialCollectionMatcher implements AbstractDistrictMatcher {
  OfficialCollectionMatcher({MunicipalityDataService? data})
      : _data = data ?? MunicipalityDataService();
  final MunicipalityDataService _data;
  final Map<String, Map<String, dynamic>> _cities = {};
  final Map<String, List<Map<String, dynamic>>> _entries = {};
  final Map<String, Map<String, String>> _names = {};

  @override
  Future<void> loadChoumeiData() async {
    for (final city in await _data.municipalities()) {
      final id = city['id'] as String;
      _cities[id] = city;
      if (_entries.containsKey(id)) continue;
      try {
        final addresses = await _data.addressesFor(id);
        if (addresses == null) continue;
        final names = {for (final area in await _data.getAreas(id))
          area['id'] as String: area['name'] as String};
        final entries = (addresses['entries'] as List).cast<Map<String, dynamic>>();
        _names[id] = names;
        _entries[id] = entries;
      } catch (error) {
        // An incomplete city must not prevent matching another city's valid table.
        debugPrint('[OfficialCollectionMatcher] $id の住所対応表を確認できません: $error');
      }
    }
  }

  List<DistrictCandidate> _candidates(GeocodedAddress address) {
    final cities = _cities.values
        .where((city) =>
            city['name'] == address.city &&
            city['prefecture_name'] == address.prefecture)
        .toList();
    if (cities.length != 1) throw OutOfAreaException();
    final city = cities.single;
    final id = city['id'] as String;
    if (!_entries.containsKey(id)) throw DistrictNotFoundException();
    final normalize = AddressNormalizer().normalize;
    final town = normalize(address.town);
    final matches = _entries[id]!.where((entry) =>
        normalize(entry['town'] as String) == town ||
        normalize(entry['lookup_town'] as String) == town);
    final unique = <String, DistrictCandidate>{};
    for (final entry in matches) {
      final areaId = entry['area_id'] as String;
      final name = _names[id]![areaId];
      if (name == null) continue;
      final region = RegionSetting(
          prefectureId: city['prefecture_id'] as String,
          prefectureName: city['prefecture_name'] as String,
          municipalityId: id,
          municipalityName: city['name'] as String,
          districtId: areaId,
          districtName: name);
      unique[areaId] = DistrictCandidate(
          districtNumber: int.tryParse(areaId.split('-').last) ?? 0,
          districtName: name,
          townName: entry['town'] as String,
          collectionAreaId: areaId,
          region: region);
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
        region: candidate.region);
  }

  @override
  List<DistrictCandidate> matchDistrictCandidates(GeocodedAddress address, {String? areaId}) => _candidates(address);
}
