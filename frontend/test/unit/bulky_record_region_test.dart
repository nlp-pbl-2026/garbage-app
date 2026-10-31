import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/providers/bulky_waste_provider.dart';
import 'package:garbage_app/services/bulky_waste_notification_service.dart';

class FakeNotifications extends BulkyWasteNotificationService {
  @override
  Future<void> scheduleNotification(ApplicationRecord record) async {}
  @override
  Future<void> cancelNotification(String recordId) async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('legacy records remain in Shimizu while new records use selected area', () async {
    final old = {
      'id': 'legacy', 'item_name': 'いす',
      'collection_date': DateTime.now().add(const Duration(days: 2)).toIso8601String(),
      'status': 'applied', 'created_at': DateTime.now().toIso8601String(),
      'updated_at': DateTime.now().toIso8601String(),
    };
    SharedPreferences.setMockInitialValues({'application_records': jsonEncode([old])});
    final prefs = await SharedPreferences.getInstance();
    final shimizu = ApplicationRecordNotifier(prefs, FakeNotifications());
    final island = ApplicationRecordNotifier(prefs, FakeNotifications(), districtId: '38201-ca-nk-oura');
    expect(shimizu.state.map((record) => record.id), ['legacy']);
    expect(island.state, isEmpty);
    await ApplicationRecordNotifier(prefs, FakeNotifications(), districtId: '38201-ca-nk-oura',
      validateCollectionDate: (_, __) async => null)
        .addRecord(itemName: '鏡', collectionDate: DateTime.now().add(const Duration(days: 3)));
    final refreshedIsland = ApplicationRecordNotifier(prefs, FakeNotifications(), districtId: '38201-ca-nk-oura');
    expect(refreshedIsland.state.single.districtId, '38201-ca-nk-oura');
    expect(ApplicationRecordNotifier(prefs, FakeNotifications()).state.map((record) => record.id), ['legacy']);
    expect((jsonDecode(prefs.getString('application_records')!) as List).length, 2);
  });

  test('an unverified island collection date is not saved or notified', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final notifier = ApplicationRecordNotifier(prefs, FakeNotifications(),
      districtId: '38201-ca-nk-oura',
      validateCollectionDate: (_, __) async => '公式収集日ではありません');
    final error = await notifier.addRecord(itemName: '鏡',
      collectionDate: DateTime.now().add(const Duration(days: 2)));
    expect(error, '公式収集日ではありません');
    expect(notifier.state, isEmpty);
    expect(prefs.getString('application_records'), isNull);
  });
  test('records with identical district IDs are separated by municipality and preserved on save', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    ApplicationRecordNotifier records(String city) => ApplicationRecordNotifier(prefs, FakeNotifications(),
        municipalityId: city, districtId: 'same-area', validateCollectionDate: (_, __) async => null);
    final a = records('90001');
    final b = records('90002'); // Both notifiers initially read the empty store.
    await a.addRecord(itemName: '試験市Aのいす', collectionDate: DateTime.now().add(const Duration(days: 3)));
    await b.addRecord(itemName: '試験町Bの机', collectionDate: DateTime.now().add(const Duration(days: 4)));
    expect(records('90001').state.single.itemName, '試験市Aのいす');
    expect(records('90002').state.single.itemName, '試験町Bの机');
    expect((jsonDecode(prefs.getString('application_records')!) as List).length, 2);
    await b.updateStatus(b.state.single.id, ApplicationStatus.completed);
    expect(records('90002').state.single.municipalityId, '90002');
    expect(records('90001').state.single.status, ApplicationStatus.applied);
  });

}
