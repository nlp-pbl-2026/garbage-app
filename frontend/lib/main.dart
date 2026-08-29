import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'providers/bulky_waste_provider.dart';
import 'providers/memo_provider.dart';
import 'providers/notification_customization_provider.dart';
import 'services/notification_customization_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('ja_JP', null);

  // MemoServiceを初期化（SharedPreferencesからメモデータを読み込む）
  final memoService = await initializeMemoService();

  // NotificationCustomizationServiceを初期化
  final prefs = await SharedPreferences.getInstance();
  final notificationCustomizationService =
      NotificationCustomizationService(prefs);

  runApp(
    ProviderScope(
      overrides: [
        memoServiceProvider.overrideWithValue(memoService),
        notificationCustomizationServiceProvider
            .overrideWithValue(notificationCustomizationService),
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
      child: const GarbageApp(),
    ),
  );
}
