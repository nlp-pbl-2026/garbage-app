import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'providers/locale_provider.dart';
import 'providers/memo_provider.dart';
import 'providers/notification_customization_provider.dart';
import 'services/notification_customization_service.dart';
import 'services/romanization_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Initialize date formatting for all supported locales
  await initializeDateFormatting('ja_JP', null);
  await initializeDateFormatting('en', null);
  await initializeDateFormatting('pt', null);
  await initializeDateFormatting('zh', null);
  await initializeDateFormatting('vi', null);

  // MemoServiceを初期化（SharedPreferencesからメモデータを読み込む）
  final memoService = await initializeMemoService();

  // NotificationCustomizationServiceを初期化
  final prefs = await SharedPreferences.getInstance();
  final notificationCustomizationService =
      NotificationCustomizationService(prefs);

  // LocaleNotifierを初期化（SharedPreferencesから言語設定を読み込む）
  final localeNotifier = LocaleNotifier();
  await localeNotifier.initialize();

  // RomanizationServiceを初期化（自治体名ローマ字データを読み込む）
  await RomanizationService.instance.load();

  runApp(
    ProviderScope(
      overrides: [
        memoServiceProvider.overrideWithValue(memoService),
        notificationCustomizationServiceProvider
            .overrideWithValue(notificationCustomizationService),
        localeProvider.overrideWith((_) => localeNotifier),
      ],
      child: const GarbageApp(),
    ),
  );
}
