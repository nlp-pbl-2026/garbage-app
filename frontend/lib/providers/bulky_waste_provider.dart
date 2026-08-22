import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/bulky_waste.dart';
import '../repositories/bulky_waste_repository.dart';
import '../services/bulky_waste_notification_service.dart';
import 'region_provider.dart';

/// SharedPreferencesのプロバイダー
///
/// アプリ起動時に [ProviderScope] の overrides で実インスタンスを注入する。
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
    'sharedPreferencesProvider must be overridden with a real instance',
  );
});

/// HTTPクライアントのプロバイダー
///
/// テスト時にモッククライアントを注入可能にするため Provider で提供する。
final httpClientProvider = Provider<http.Client>((ref) {
  return http.Client();
});

/// 粗大ごみリポジトリのシングルトンプロバイダー
///
/// [BulkyWasteRepository] のインスタンスを提供する。
/// SharedPreferences と HTTP クライアントを注入し、
/// アプリ全体で1つのインスタンスを共有する。
final bulkyWasteRepositoryProvider = Provider<BulkyWasteRepository>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  final client = ref.watch(httpClientProvider);
  return BulkyWasteRepository(client: client, prefs: prefs);
});

/// 自治体設定プロバイダー（地域設定に連動）
///
/// [regionSettingProvider] を監視し、設定された市区町村の粗大ごみ情報を取得する。
/// 地域設定が null の場合は null を返す。
/// API取得に成功した場合は [CachedResult] に最新データを格納し、
/// キャッシュフォールバック時は [CachedResult.isStale] = true となる。
final municipalityConfigProvider =
    FutureProvider<CachedResult<MunicipalityConfig>?>((ref) async {
  final regionSettingAsync = ref.watch(regionSettingProvider);
  final regionSetting = regionSettingAsync.valueOrNull;

  if (regionSetting == null) return null;

  final repo = ref.watch(bulkyWasteRepositoryProvider);
  return repo.getMunicipalityConfig(regionSetting.municipalityId);
});

/// 品目一覧検索・ソート用のクエリパラメータ
///
/// [FutureProvider.family] のファミリーキーとして使用し、
/// 検索条件やソート順の変更に応じてプロバイダーを再実行する。
class BulkyWasteQuery {
  /// 自治体ID（5桁コード）
  final String municipalityId;

  /// 検索キーワード（品目名・カテゴリの部分一致）
  final String? search;

  /// ソート基準
  final SortBy? sortBy;

  /// ソート順序
  final SortOrder? sortOrder;

  const BulkyWasteQuery({
    required this.municipalityId,
    this.search,
    this.sortBy,
    this.sortOrder,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BulkyWasteQuery &&
          runtimeType == other.runtimeType &&
          municipalityId == other.municipalityId &&
          search == other.search &&
          sortBy == other.sortBy &&
          sortOrder == other.sortOrder;

  @override
  int get hashCode =>
      municipalityId.hashCode ^
      search.hashCode ^
      sortBy.hashCode ^
      sortOrder.hashCode;

  @override
  String toString() =>
      'BulkyWasteQuery(municipalityId: $municipalityId, search: $search, '
      'sortBy: $sortBy, sortOrder: $sortOrder)';
}

/// 品目一覧プロバイダー（検索・ソート対応）
///
/// [BulkyWasteQuery] をキーとして品目一覧を取得する。
/// 検索キーワード・ソート基準・ソート順序の組み合わせに応じて
/// 異なるプロバイダーインスタンスが生成される。
final bulkyWasteItemsProvider =
    FutureProvider.family<CachedResult<BulkyWasteItemList>?, BulkyWasteQuery>(
        (ref, query) async {
  final repo = ref.watch(bulkyWasteRepositoryProvider);
  return repo.getItems(
    query.municipalityId,
    search: query.search,
    sortBy: query.sortBy,
    sortOrder: query.sortOrder,
  );
});

/// 申し込み記録のStateNotifier
///
/// ローカルの申し込み記録（SharedPreferences）を管理する。
/// 記録の作成・ステータス更新・アーカイブ（完了移動）を処理し、
/// バリデーション（品目名空/過去日付）も行う。
/// 収集日24時間前にローカル通知をスケジュールする。
class ApplicationRecordNotifier extends StateNotifier<List<ApplicationRecord>> {
  final SharedPreferences _prefs;
  final BulkyWasteNotificationService _notificationService;

  /// SharedPreferences保存キー
  static const String _storageKey = 'application_records';

  ApplicationRecordNotifier(this._prefs, this._notificationService)
      : super([]) {
    _loadRecords();
  }

  /// SharedPreferencesから記録を読み込む
  void _loadRecords() {
    final jsonString = _prefs.getString(_storageKey);
    if (jsonString == null) {
      state = [];
      return;
    }
    try {
      final jsonList = jsonDecode(jsonString) as List<dynamic>;
      state = jsonList
          .map((e) => ApplicationRecord.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      state = [];
    }
  }

  /// 記録をSharedPreferencesに永続化する
  Future<void> _saveRecords() async {
    final jsonList = state.map((e) => e.toJson()).toList();
    await _prefs.setString(_storageKey, jsonEncode(jsonList));
  }

  /// 新しい申し込み記録を作成する
  ///
  /// バリデーション:
  /// - [itemName] が空白のみ / 空文字の場合はエラー
  /// - [itemName] が50文字を超える場合はエラー
  /// - [collectionDate] が過去日付の場合はエラー
  ///
  /// 成功時は記録をリストに追加し永続化する。
  /// 戻り値: 成功なら null、失敗ならエラーメッセージ。
  Future<String?> addRecord({
    required String itemName,
    required DateTime collectionDate,
  }) async {
    // バリデーション: 品目名
    final trimmedName = itemName.trim();
    if (trimmedName.isEmpty) {
      return '品目名を入力してください';
    }
    if (trimmedName.length > ApplicationRecord.maxItemNameLength) {
      return '品目名は${ApplicationRecord.maxItemNameLength}文字以内で入力してください';
    }

    // バリデーション: 収集予定日（今日以降）
    final today = DateTime.now();
    final todayDateOnly = DateTime(today.year, today.month, today.day);
    final collectionDateOnly = DateTime(
      collectionDate.year,
      collectionDate.month,
      collectionDate.day,
    );
    if (collectionDateOnly.isBefore(todayDateOnly)) {
      return '収集予定日は今日以降の日付を選択してください';
    }

    // 記録作成
    final now = DateTime.now();
    final record = ApplicationRecord(
      id: _generateId(),
      itemName: trimmedName,
      collectionDate: collectionDateOnly,
      status: ApplicationStatus.applied,
      createdAt: now,
      updatedAt: now,
    );

    state = [...state, record];
    await _saveRecords();

    // 通知をスケジュール
    await _notificationService.scheduleNotification(record);

    return null;
  }

  /// 記録のステータスを更新する
  ///
  /// [id] で特定される記録のステータスを [newStatus] に変更し永続化する。
  /// 該当記録が存在しない場合は何もしない。
  /// ステータスが completed に変更された場合は通知をキャンセルする。
  Future<void> updateStatus(String id, ApplicationStatus newStatus) async {
    final index = state.indexWhere((r) => r.id == id);
    if (index == -1) return;

    final updatedRecord = state[index].copyWithStatus(newStatus);
    final newState = [...state];
    newState[index] = updatedRecord;
    state = newState;
    await _saveRecords();

    // completed の場合は通知をキャンセル、それ以外は再スケジュール
    if (newStatus == ApplicationStatus.completed) {
      await _notificationService.cancelNotification(id);
    } else {
      await _notificationService.scheduleNotification(updatedRecord);
    }
  }

  /// 完了済み記録をアーカイブする（ステータスを completed に設定）
  ///
  /// [id] で特定される記録のステータスを [ApplicationStatus.completed] に変更する。
  Future<void> archiveRecord(String id) async {
    await updateStatus(id, ApplicationStatus.completed);
  }

  /// アクティブな記録一覧を取得する（completed 以外）
  List<ApplicationRecord> get activeRecords =>
      state.where((r) => r.status != ApplicationStatus.completed).toList();

  /// アーカイブ済み（completed）の記録一覧を取得する
  List<ApplicationRecord> get archivedRecords =>
      state.where((r) => r.status == ApplicationStatus.completed).toList();

  /// 全アクティブ記録の通知を再スケジュールする
  ///
  /// アプリ起動時や設定変更時に呼び出す。
  /// completed 以外の記録に対して通知をスケジュールし直す。
  Future<void> rescheduleAllNotifications() async {
    await _notificationService.rescheduleAll(state);
  }

  /// ユニークIDを生成する
  ///
  /// DateTimeベースのシンプルなID生成。
  String _generateId() {
    final now = DateTime.now();
    return '${now.millisecondsSinceEpoch}_${now.microsecond}';
  }
}

/// 粗大ごみ通知サービスのプロバイダー
///
/// [BulkyWasteNotificationService] のインスタンスを提供する。
final bulkyWasteNotificationServiceProvider =
    Provider<BulkyWasteNotificationService>((ref) {
  return BulkyWasteNotificationService();
});

/// 申し込み記録プロバイダー
///
/// [ApplicationRecordNotifier] によるローカル記録の状態管理を提供する。
/// SharedPreferences に永続化された記録を読み込み、
/// 追加・ステータス更新・アーカイブ操作を公開する。
/// 通知サービスを注入し、収集日前のリマインダー通知を管理する。
final applicationRecordsProvider =
    StateNotifierProvider<ApplicationRecordNotifier, List<ApplicationRecord>>(
  (ref) {
    final prefs = ref.watch(sharedPreferencesProvider);
    final notificationService =
        ref.watch(bulkyWasteNotificationServiceProvider);
    return ApplicationRecordNotifier(prefs, notificationService);
  },
);
