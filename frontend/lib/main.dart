import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'providers/bulky_waste_provider.dart';
import 'providers/memo_provider.dart';
import 'providers/notification_customization_provider.dart';
import 'providers/settings_provider.dart';
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

  // ProviderContainer を先に生成し、通知サービスとナビゲーションハンドラを
  // アプリ全体で共有する同一インスタンスとして起動フローに配線する。
  final container = ProviderContainer(
    overrides: [
      memoServiceProvider.overrideWithValue(memoService),
      notificationCustomizationServiceProvider
          .overrideWithValue(notificationCustomizationService),
      sharedPreferencesProvider.overrideWithValue(prefs),
    ],
  );

  // 起動時の通知初期化と復元（要件 5.1, 6.2, 6.3）。
  // 通知に起因する失敗でアプリ起動がクラッシュしないよう try/catch で保護する。
  try {
    final notificationService = container.read(notificationServiceProvider);
    final navigationHandler =
        container.read(notificationNavigationHandlerProvider);

    // 通知タップ応答をナビゲーションハンドラへ接続する（要件 5.1）。
    await notificationService.initialize(
      onDidReceiveNotificationResponse:
          navigationHandler.notificationResponseCallback,
    );
    // 保存済み設定を読み込み、有効なら再スケジュールする（要件 6.2, 6.3）。
    await notificationService.restoreOnStartup();
  } catch (e, st) {
    debugPrint('[main] 通知の起動時初期化に失敗しました: $e\n$st');
  }

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const GarbageApp(),
    ),
  );
}
