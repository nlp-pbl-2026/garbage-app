import 'dart:convert';

import 'package:flutter/services.dart' show AssetBundle, rootBundle;

/// Published metadata is kept separate from the generated, source checked dates.
class MunicipalityDataService {
  MunicipalityDataService({AssetBundle? bundle}) : _bundle = bundle ?? rootBundle;
  final AssetBundle _bundle;
  Map<String, dynamic>? _registry;
  Map<String, dynamic>? _calendar;
  Map<String, dynamic>? _addresses;

  Future<Map<String, dynamic>> get registry async =>
      _registry ??= jsonDecode(await _bundle.loadString('assets/data/municipality_registry.json')) as Map<String, dynamic>;

  Future<Map<String, dynamic>> get calendar async =>
      _calendar ??= jsonDecode(await _bundle.loadString('assets/data/municipality_calendar.json')) as Map<String, dynamic>;

  Future<Map<String, dynamic>> get addresses async =>
      _addresses ??= jsonDecode(await _bundle.loadString('assets/data/municipality_addresses.json')) as Map<String, dynamic>;

  Future<List<Map<String, dynamic>>> getAreas() async {
    final data = await registry;
    return (data['collection_areas'] as List).cast<Map<String, dynamic>>();
  }

  /// A legacy ID is accepted only if it has exactly one official collection area.
  Future<List<String>> areaCandidates(String districtId) async {
    final data = await registry;
    final areas = await getAreas();
    if (areas.any((area) => area['id'] == districtId)) return [districtId];
    return ((data['legacy_district_candidates'] as Map<String, dynamic>?)?[districtId] as List?)?.cast<String>() ?? [];
  }

  Future<Map<String, dynamic>?> area(String districtId) async {
    final candidates = await areaCandidates(districtId);
    if (candidates.length != 1) {
      return null;
    }
    for (final entry in await getAreas()) {
      if (entry['id'] == candidates.single) return entry;
    }
    return null;
  }

  Future<Map<String, dynamic>?> verifiedCalendar(String districtId) async {
    final entry = await area(districtId);
    if (entry == null) return null;
    final catalog = await registry;
    final bundle = await calendar;
    if (bundle['version'] != catalog['version'] ||
        bundle['valid_from'] != catalog['valid_from'] ||
        bundle['valid_to'] != catalog['valid_to']) {
      return null;
    }
    final record = (bundle['calendars'] as Map<String, dynamic>)[entry['calendar_id']];
    if (record is! Map<String, dynamic> || record['verification_status'] != 'checked') {
      return null;
    }
    return record;
  }

  Future<List<Map<String, dynamic>>> addressCandidates(String town) async {
    final data = await addresses;
    final normalized = _norm(town);
    final entries = (data['entries'] as List).cast<Map<String, dynamic>>();
    return entries.where((entry) => entry['lookup_town'] == normalized || entry['town'] == normalized).toList();
  }

  String _norm(String text) => text.replaceAll(RegExp(r'[\s　]'), '').replaceAll('１', '1').replaceAll('２', '2');
}
