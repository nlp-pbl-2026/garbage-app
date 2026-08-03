import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/memo_service.dart';

/// MemoServiceのプロバイダー
///
/// アプリ起動時にSharedPreferencesを取得してMemoServiceを初期化し、
/// ProviderScopeのoverridesで実インスタンスを設定する。
/// 未初期化状態でアクセスされた場合はUnimplementedErrorをスローする。
final memoServiceProvider = Provider<MemoService>((ref) {
  throw UnimplementedError(
    'memoServiceProvider must be overridden with an initialized MemoService instance',
  );
});

/// 月間メモデータのプロバイダー（月ごとにメモがある日付セットを提供）
///
/// パラメータのDateTimeから年月を取得し、その月にメモが存在する日付のSetを返す。
/// カレンダー画面でメモインジケーターの表示判定に使用する。
final monthlyMemosProvider =
    Provider.family<Set<DateTime>, DateTime>((ref, month) {
  final memoService = ref.watch(memoServiceProvider);
  return memoService.getMemoDatesForMonth(month.year, month.month);
});

/// 特定日付のメモ取得用プロバイダー
///
/// 指定された日付のメモテキストを返す。メモが存在しない場合はnullを返す。
/// メモダイアログでの既存メモ表示に使用する。
final memoForDateProvider = Provider.family<String?, DateTime>((ref, date) {
  final memoService = ref.watch(memoServiceProvider);
  return memoService.getMemo(date);
});

/// MemoServiceを初期化するヘルパー関数
///
/// SharedPreferencesのインスタンスを取得し、MemoServiceを生成・初期化して返す。
/// main.dart のアプリ起動フローで呼び出す。
Future<MemoService> initializeMemoService() async {
  final prefs = await SharedPreferences.getInstance();
  final memoService = MemoService(prefs);
  await memoService.init();
  return memoService;
}
