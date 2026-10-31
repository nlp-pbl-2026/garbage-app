import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../helpers/municipality_assets.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('dexterous.com/flutter/local_notifications');

  test('rapid municipality switches cancel old schedules before installing the latest city’s notifications', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    addTearDown(() => debugDefaultTargetPlatformOverride = null);
    SharedPreferences.setMockInitialValues({'reminder_enabled': true});
    final entered = Completer<void>();
    final release = Completer<void>();
    final installed = <Map<String, dynamic>>[];
    var first = true;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'initialize') return true;
      if (call.method == 'cancelAll') installed.clear();
      if (call.method == 'zonedSchedule') {
        if (first) {
          first = false;
          entered.complete();
          await release.future;
        }
        installed.add(Map<String, dynamic>.from(call.arguments as Map));
      }
      return null;
    });
    addTearDown(() => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null));
    final service = NotificationService(now: () => DateTime(2026, 11, 1),
        data: MunicipalityDataService(bundle: MunicipalityBundle(multiMunicipalityAssets())));
    final old = service.updateDistrict('same-area', municipalityId: '90001');
    await entered.future;
    final current = service.updateDistrict('same-area', municipalityId: '90002');
    release.complete();
    await Future.wait([old, current]);
    expect(installed.length, 2);
    for (final notification in installed) {
      expect(notification['body'], contains('試験町B回収物'));
      expect(jsonDecode(notification['payload'] as String)['municipality_id'], '90002');
    }
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('notification_municipality_id'), '90002');
    expect(prefs.getString('notification_district_id'), 'same-area');
  });
}
