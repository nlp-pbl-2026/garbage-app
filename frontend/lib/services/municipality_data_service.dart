import 'dart:convert';
import 'package:flutter/services.dart' show AssetBundle, rootBundle;
import '../models/garbage_item.dart';
import '../models/collection_status.dart';

/// Offline UI metadata generated from the same registries as the backend.
/// Missing data never falls back to another municipality.
class MunicipalityDataService {
  MunicipalityDataService({AssetBundle? bundle})
      : _bundle = bundle ?? rootBundle;
  final AssetBundle _bundle;
  final Map<String, Future<Map<String, dynamic>>> _files = {};

  Future<Map<String, dynamic>> _load(String path) => _files.putIfAbsent(
      path,
      () async =>
          jsonDecode(await _bundle.loadString(path)) as Map<String, dynamic>);

  Future<List<Map<String, dynamic>>> municipalities() async {
    final catalog = await _load('assets/data/municipality_catalog.json');
    if (catalog['schema_version'] != 1) {
      throw const FormatException('Unsupported municipality catalog');
    }
    final entries =
        (catalog['municipalities'] as List).cast<Map<String, dynamic>>();
    if (entries.map((e) => e['id']).toSet().length != entries.length) {
      throw const FormatException('Duplicate municipality ID');
    }
    return entries;
  }

  Future<Map<String, dynamic>?> municipality(String id) async {
    for (final entry in await municipalities()) {
      if (entry['id'] == id) return entry;
    }
    return null;
  }

  Future<Map<String, dynamic>> registryFor(String municipalityId) async {
    final city = await municipality(municipalityId);
    if (city == null) throw StateError('指定された自治体は未対応です。');
    final result = await _load(city['registry_asset'] as String);
    if (result['municipality_id'] != municipalityId ||
        result['version'] != city['version']) {
      throw const FormatException('Registry municipality/version mismatch');
    }
    return result;
  }

  // Compatibility accessors for existing Matsuyama tooling.
  Future<Map<String, dynamic>> get registry => registryFor('38201');
  Future<Map<String, dynamic>> get calendar =>
      calendarFor('38201', 'matsuyama_hojo');
  Future<Map<String, dynamic>> get addresses async =>
      (await addressesFor('38201'))!;

  Future<Map<String, dynamic>?> addressesFor(String municipalityId) async {
    final city = await municipality(municipalityId);
    final path = city?['addresses_asset'] as String?;
    if (path == null) return null;
    final result = await _load(path);
    if (result['municipality_id'] != municipalityId ||
        result['version'] != (await registryFor(municipalityId))['version']) {
      throw const FormatException('Address municipality/version mismatch');
    }
    return result;
  }

  Future<List<Map<String, dynamic>>> getAreas(
      [String municipalityId = '38201']) async {
    if (await municipality(municipalityId) == null) return [];
    return ((await registryFor(municipalityId))['collection_areas'] as List)
        .cast<Map<String, dynamic>>()
        .map((area) => {...area, 'name': area['display_name'] ?? area['name']})
        .toList();
  }

  Future<List<String>> areaCandidates(String districtId,
      {String municipalityId = '38201'}) async {
    if (await municipality(municipalityId) == null) return [];
    final data = await registryFor(municipalityId);
    final areas = await getAreas(municipalityId);
    if (areas.any((a) => a['id'] == districtId)) return [districtId];
    final candidates = ((data['legacy_district_candidates']
                as Map<String, dynamic>?)?[districtId] as List?)
            ?.cast<String>() ??
        [];
    return candidates;
  }

  Future<Map<String, dynamic>?> area(String districtId,
      {String municipalityId = '38201'}) async {
    final candidates =
        await areaCandidates(districtId, municipalityId: municipalityId);
    if (candidates.length != 1) return null;
    for (final entry in await getAreas(municipalityId)) {
      if (entry['id'] == candidates.single) return entry;
    }
    return null;
  }

  Future<Map<String, dynamic>> profile(
      String municipalityId, String profileId) async {
    final city = await municipality(municipalityId);
    final result = (city?['profiles'] as Map<String, dynamic>?)?[profileId];
    if (result is! Map<String, dynamic> || result['categories'] is! Map) {
      throw StateError('自治体の分別設定を確認できません。');
    }
    return result;
  }

  Future<Map<String, dynamic>> calendarFor(
      String municipalityId, String profileId) async {
    final config = await profile(municipalityId, profileId);
    return _load(config['calendar_asset'] as String);
  }

  Future<List<GarbageCategory>> categories(String districtId,
      {String municipalityId = '38201'}) async {
    final entry = await area(districtId, municipalityId: municipalityId);
    if (entry == null) return [];
    final profileId = entry['rule_profile_id'] as String;
    final definitions = (await profile(municipalityId, profileId))['categories']
        as Map<String, dynamic>;
    final streams = <String, GarbageCategory>{};
    for (final definition in definitions.values.cast<Map<String, dynamic>>()) {
      final id = definition['collection_type_id'] as String?;
      if (id == null) continue;
      final cutoff = definition['cutoff'] as String?;
      if (cutoff == null ||
          !RegExp(r'^(?:[01]\d|2[0-3]):[0-5]\d$').hasMatch(cutoff)) {
        throw const FormatException('Invalid collection cutoff');
      }
      if (streams.containsKey(id)) {
        if (streams[id]!.cutoff != cutoff) {
          throw const FormatException('Conflicting collection cutoff');
        }
        continue;
      }
      if (municipalityId == '38201') {
        final legacy = GarbageCategoryExtension.fromString(id);
        if (legacy.cutoff != cutoff) {
          throw const FormatException(
              'Matsuyama cutoff changed; update compatibility mapping');
        }
        streams[id] = legacy;
      } else {
        final color = definition['color'] as String?;
        if (color != null && !RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(color)) {
          throw const FormatException('Invalid category color');
        }
        streams[id] = GarbageCategory.regional(
            id: id,
            scope: '$municipalityId/$profileId',
            displayName: (definition['collection_name'] ?? definition['name']) as String,
            cutoff: cutoff,
            colorValue: color == null
                ? null
                : int.parse('FF${color.substring(1)}', radix: 16));
      }
    }
    final result = streams.values.toList();
    if (municipalityId == '38201') {
      const order = ['burnable', 'paper', 'metal_glass', 'landfill', 'mercury', 'plastic', 'petBottle', 'cans', 'bottles', 'bulky'];
      result.sort((a, b) => order.indexOf(a.id).compareTo(order.indexOf(b.id)));
    }
    return result;
  }

  Future<Map<String, dynamic>?> verifiedCalendar(String districtId,
      {String municipalityId = '38201'}) async {
    final entry = await area(districtId, municipalityId: municipalityId);
    if (entry == null) return null;
    final registry = await registryFor(municipalityId);
    final bundle =
        await calendarFor(municipalityId, entry['rule_profile_id'] as String);
    if (bundle['municipality_id'] != municipalityId ||
        bundle['version'] != registry['version'] ||
        bundle['valid_from'] != registry['valid_from'] ||
        bundle['valid_to'] != registry['valid_to']) {
      return null;
    }
    final record =
        (bundle['calendars'] as Map<String, dynamic>)[entry['calendar_id']];
    if (record is! Map<String, dynamic> ||
        !['checked', 'partially_checked'].contains(record['verification_status'])) {
      return null;
    }
    final verification = record['collection_type_verification'];
    if (verification != null || record['verification_status'] == 'partially_checked') {
      final definitions = (await profile(municipalityId, entry['rule_profile_id'] as String))['categories'] as Map<String, dynamic>;
      final streams = definitions.values.cast<Map<String, dynamic>>()
          .map((definition) => definition['collection_type_id']).whereType<String>().toSet();
      if (verification is! Map<String, dynamic> || verification.keys.toSet().difference(streams).isNotEmpty ||
          streams.difference(verification.keys.toSet()).isNotEmpty) { return null; }
      if (verification.values.any((info) => info is! Map<String, dynamic> ||
          !['checked', 'unverified'].contains(info['status']))) { return null; }
      final unknown = verification.values.cast<Map<String, dynamic>>().where((info) => info['status'] == 'unverified').toList();
      if (unknown.isNotEmpty != (record['verification_status'] == 'partially_checked') || unknown.length == streams.length ||
          unknown.any((info) => info['message'] is! String || info['source_url'] is! String ||
              (info['message'] as String).isEmpty || (info['source_url'] as String).isEmpty)) { return null; }
    }
    return record;
  }

  Future<Map<String, CollectionStatus>> collectionStatuses(String districtId,
      {String municipalityId = '38201'}) async {
    final record = await verifiedCalendar(districtId, municipalityId: municipalityId);
    final types = await categories(districtId, municipalityId: municipalityId);
    final verification = record?['collection_type_verification'] as Map<String, dynamic>?;
    return {for (final type in types) type.id:
      record == null ? const CollectionStatus('unverified_data') :
        verification?[type.id] == null ? const CollectionStatus('checked') :
          CollectionStatus.fromJson(verification![type.id] as Map<String, dynamic>)};
  }
}
