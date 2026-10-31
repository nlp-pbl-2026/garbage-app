import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show FlutterError;

/// Synthetic metadata only; tests never require official calendar dates.
Map<String, dynamic> matsuyamaCatalog() => {
      'schema_version': 1,
      'municipalities': [
        {
          'id': '38201',
          'version': 'test-v1',
          'name': '松山市',
          'prefecture_id': '38',
          'prefecture_name': '愛媛県',
          'registry_asset': 'assets/data/municipality_registry.json',
          'addresses_asset': 'assets/data/municipality_addresses.json',
          'profiles': {
            for (final profile in ['matsuyama_hojo', 'nakajima'])
              profile: {
                'calendar_asset': 'assets/data/municipality_calendar.json',
                'categories': {
                  for (final id in [
                    'combustible',
                    'paper',
                    'metal_glass',
                    'landfill',
                    'mercury',
                    'plastic_packaging',
                    'pet_bottle',
                    if (profile == 'nakajima') ...['cans', 'bottles', 'bulky']
                  ])
                    id: {
                      'name': id,
                      'collection_type_id': id,
                      'cutoff': id == 'combustible' ? '07:00' : '08:00'
                    },
                },
              },
          },
        }
      ],
    };

Map<String, String> withMatsuyamaCatalog(Map<String, String> files) => {
      'assets/data/municipality_catalog.json': jsonEncode(matsuyamaCatalog()),
      ...files,
    };

Map<String, String> multiMunicipalityAssets() {
  final cities = <Map<String, dynamic>>[];
  final files = <String, String>{};
  for (final id in ['90001', '90002']) {
    final name = id == '90001' ? '試験市A' : '試験町B';
    final version = '$id-v1';
    cities.add({
      'id': id,
      'name': name,
      'version': version,
      'prefecture_id': '38',
      'prefecture_name': '愛媛県',
      'registry_asset': '$id-registry',
      'addresses_asset': '$id-addresses',
      'profiles': {
        'nakajima': {
          'calendar_asset': '$id-calendar',
          'categories': {
            'burn': {
              'name': '$name回収物',
              'collection_type_id': 'burnable',
              'cutoff': id == '90001' ? '08:30' : '09:15',
              'color': id == '90001' ? '#112233' : '#abcdef'
            },
            'alias': {
              'name': '同じ収集区分の別分類',
              'collection_type_id': 'burnable',
              'cutoff': id == '90001' ? '08:30' : '09:15'
            },
            'carry': {'name': '持込対象'},
          },
        }
      },
    });
    files['$id-registry'] = jsonEncode({
      'municipality_id': id,
      'version': version,
      'valid_from': '2026-01-01',
      'valid_to': '2026-12-31',
      'collection_areas': [
        {
          'id': 'same-area',
          'name': '$name地区',
          'calendar_id': 'same-calendar',
          'rule_profile_id': 'nakajima'
        }
      ],
      'calendars': [
        {'id': 'same-calendar', 'rule_profile_id': 'nakajima'}
      ],
    });
    files['$id-calendar'] = jsonEncode({
      'municipality_id': id,
      'version': version,
      'valid_from': '2026-01-01',
      'valid_to': '2026-12-31',
      'calendars': {
        'same-calendar': {
          'verification_status': 'checked',
          'days': {
            id == '90001' ? '2026-11-02' : '2026-11-03': ['burnable'],
            '2027-01-01': [
              'burnable'
            ], // Deliberately outside the published period.
          }
        }
      },
    });
    files['$id-addresses'] = jsonEncode({
      'municipality_id': id,
      'version': version,
      'entries': [
        {'town': '同名町', 'lookup_town': '同名町', 'area_id': 'same-area'}
      ],
    });
  }
  files['assets/data/municipality_catalog.json'] = jsonEncode({
    'schema_version': 1,
    'municipalities': cities,
  });
  return files;
}

class MunicipalityBundle extends CachingAssetBundle {
  MunicipalityBundle(this.files);
  final Map<String, String> files;
  @override
  Future<ByteData> load(String key) async {
    if (!files.containsKey(key)) throw FlutterError('Missing asset $key');
    return ByteData.sublistView(Uint8List.fromList(utf8.encode(files[key]!)));
  }
}
