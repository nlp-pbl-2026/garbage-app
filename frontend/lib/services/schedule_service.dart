import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

import '../models/collection_schedule.dart';
import '../models/garbage_item.dart';

/// 収集スケジュールの管理を担当するサービスクラス
///
/// ローカルJSONファイルから収集ルール（CollectionRule）を読み込み、
/// 月間スケジュール生成・日付フィルタリング・次回収集日計算の機能を提供する。
/// 初回読み込み後はメモリにキャッシュする。
class ScheduleService {
  /// 収集ルールデータのキャッシュ
  List<CollectionRule>? _rulesCache;

  /// 当日の収集を「過去」として扱うカットオフ時刻（12:00）
  ///
  /// この時刻以降にアプリを開いた場合、当日の収集は既に完了とみなし
  /// 「次の収集日」から除外する（翌日以降を表示する）。
  static const int _cutoffHour = 12;

  /// 「次の収集日」の起算日を取得する
  ///
  /// 現在時刻がカットオフ時刻（12:00）以降の場合は翌日を返す。
  /// それより前の場合は今日を返す。
  DateTime _getEffectiveStartDate() {
    final now = DateTime.now();
    if (now.hour >= _cutoffHour) {
      // 12時以降は翌日から検索
      return DateTime(now.year, now.month, now.day + 1);
    }
    return DateTime(now.year, now.month, now.day);
  }

  /// 収集ルールデータを読み込み、キャッシュする
  ///
  /// キャッシュ済みの場合はキャッシュから返す。
  Future<List<CollectionRule>> _loadRules() async {
    if (_rulesCache != null) {
      return _rulesCache!;
    }

    final jsonString =
        await rootBundle.loadString('assets/data/collection_schedules.json');
    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    _rulesCache =
        jsonList
            .map(
              (item) => CollectionRule.fromJson(item as Map<String, dynamic>),
            )
            .toList();
    return _rulesCache!;
  }

  /// 指定地区の月間収集スケジュールを取得する
  ///
  /// [districtId] 地区ID、[year] 年、[month] 月を指定し、
  /// 各日付に対応するScheduleEntryのリストをMapで返す。
  /// Mapのキーは年月日のみで比較するDateTime（時刻は00:00:00）。
  Future<Map<DateTime, List<ScheduleEntry>>> getMonthlySchedule(
    String districtId,
    int year,
    int month,
  ) async {
    final rules = await _loadRules();

    // 指定地区のルールを取得
    final districtRules =
        rules.where((rule) => rule.districtId == districtId).toList();

    final Map<DateTime, List<ScheduleEntry>> schedule = {};

    for (final rule in districtRules) {
      // 各ルールから指定月の日付リストを生成
      final dates = rule.generateDatesForMonth(year, month);

      for (final date in dates) {
        // キーは年月日のみ（時刻なし）のDateTimeとする
        final dateKey = DateTime(date.year, date.month, date.day);

        final entry = ScheduleEntry(
          districtId: districtId,
          category: rule.category,
          date: dateKey,
        );

        if (schedule.containsKey(dateKey)) {
          schedule[dateKey]!.add(entry);
        } else {
          schedule[dateKey] = [entry];
        }
      }
    }

    return schedule;
  }

  /// 指定日付の収集予定リストを取得する
  ///
  /// [districtId] 地区ID、[date] 対象日付を指定し、
  /// その日に予定されている収集のScheduleEntryリストを返す。
  /// 該当するスケジュールがない場合は空リストを返す。
  Future<List<ScheduleEntry>> getScheduleForDate(
    String districtId,
    DateTime date,
  ) async {
    final schedule = await getMonthlySchedule(
      districtId,
      date.year,
      date.month,
    );

    final dateKey = DateTime(date.year, date.month, date.day);
    return schedule[dateKey] ?? [];
  }

  /// 次回の収集予定を取得する
  ///
  /// [districtId] 地区IDを指定し、今日以降で最も近い収集予定を返す。
  /// 当月と翌月のスケジュールから探索する。
  /// 該当する予定がない場合はnullを返す。
  Future<ScheduleEntry?> getNextCollection(String districtId) async {
    final now = DateTime.now();
    final today = _getEffectiveStartDate();

    // 当月のスケジュールを取得
    final currentMonthSchedule = await getMonthlySchedule(
      districtId,
      today.year,
      today.month,
    );

    // 翌月のスケジュールを取得
    final nextMonth =
        today.month == 12
            ? DateTime(today.year + 1, 1, 1)
            : DateTime(today.year, today.month + 1, 1);
    final nextMonthSchedule = await getMonthlySchedule(
      districtId,
      nextMonth.year,
      nextMonth.month,
    );

    // 全エントリを収集して今日以降のものをフィルタ
    final allEntries = <ScheduleEntry>[];

    for (final entries in currentMonthSchedule.values) {
      allEntries.addAll(entries);
    }
    for (final entries in nextMonthSchedule.values) {
      allEntries.addAll(entries);
    }

    // 今日以降のエントリのみに絞る
    final futureEntries =
        allEntries.where((entry) {
          final entryDate = DateTime(
            entry.date.year,
            entry.date.month,
            entry.date.day,
          );
          return !entryDate.isBefore(today);
        }).toList();

    if (futureEntries.isEmpty) {
      return null;
    }

    // 日付でソートして最も近いものを返す
    futureEntries.sort((a, b) => a.date.compareTo(b.date));
    return futureEntries.first;
  }

  /// 指定カテゴリの次回収集日を取得する
  ///
  /// [districtId] 地区ID、[categoryId] カテゴリ文字列を指定し、
  /// 今日以降で最も近い該当カテゴリの収集日を返す。
  /// 当月と翌月のスケジュールから探索する。
  /// 該当する予定がない場合はnullを返す。
  Future<DateTime?> getNextCollectionDate(
    String districtId,
    String categoryId,
  ) async {
    final now = DateTime.now();
    final today = _getEffectiveStartDate();

    // カテゴリ文字列をenumに変換
    final GarbageCategory category;
    try {
      category = GarbageCategoryExtension.fromString(categoryId);
    } catch (_) {
      return null;
    }

    // 当月のスケジュールを取得
    final currentMonthSchedule = await getMonthlySchedule(
      districtId,
      today.year,
      today.month,
    );

    // 翌月のスケジュールを取得
    final nextMonth =
        today.month == 12
            ? DateTime(today.year + 1, 1, 1)
            : DateTime(today.year, today.month + 1, 1);
    final nextMonthSchedule = await getMonthlySchedule(
      districtId,
      nextMonth.year,
      nextMonth.month,
    );

    // 全エントリを収集してフィルタ
    final allEntries = <ScheduleEntry>[];

    for (final entries in currentMonthSchedule.values) {
      allEntries.addAll(entries);
    }
    for (final entries in nextMonthSchedule.values) {
      allEntries.addAll(entries);
    }

    // 指定カテゴリかつ今日以降のエントリのみに絞る
    final futureEntries =
        allEntries.where((entry) {
          final entryDate = DateTime(
            entry.date.year,
            entry.date.month,
            entry.date.day,
          );
          return entry.category == category && !entryDate.isBefore(today);
        }).toList();

    if (futureEntries.isEmpty) {
      return null;
    }

    // 日付でソートして最も近いものを返す
    futureEntries.sort((a, b) => a.date.compareTo(b.date));
    return futureEntries.first.date;
  }

  /// 指定カテゴリの今後の収集日リストを取得する
  ///
  /// [districtId] 地区ID、[categoryId] カテゴリ文字列、[count] 取得件数を指定し、
  /// 今日以降の該当カテゴリの収集日を最大[count]件返す。
  /// 当月から最大3ヶ月先まで探索する。
  Future<List<DateTime>> getUpcomingCollectionDates(
    String districtId,
    String categoryId, {
    int count = 10,
  }) async {
    final now = DateTime.now();
    final today = _getEffectiveStartDate();

    final GarbageCategory category;
    try {
      category = GarbageCategoryExtension.fromString(categoryId);
    } catch (_) {
      return [];
    }

    final allEntries = <ScheduleEntry>[];

    // 当月から3ヶ月分を探索
    for (int i = 0; i < 3; i++) {
      final targetMonth = DateTime(today.year, today.month + i, 1);
      final monthSchedule = await getMonthlySchedule(
        districtId,
        targetMonth.year,
        targetMonth.month,
      );
      for (final entries in monthSchedule.values) {
        allEntries.addAll(entries);
      }
    }

    // 指定カテゴリかつ今日以降のエントリのみに絞る
    final futureEntries = allEntries.where((entry) {
      final entryDate = DateTime(entry.date.year, entry.date.month, entry.date.day);
      return entry.category == category && !entryDate.isBefore(today);
    }).toList();

    // 日付でソートして重複除去
    futureEntries.sort((a, b) => a.date.compareTo(b.date));
    final uniqueDates = <DateTime>[];
    for (final entry in futureEntries) {
      final dateKey = DateTime(entry.date.year, entry.date.month, entry.date.day);
      if (!uniqueDates.any((d) => d.year == dateKey.year && d.month == dateKey.month && d.day == dateKey.day)) {
        uniqueDates.add(dateKey);
      }
      if (uniqueDates.length >= count) break;
    }

    return uniqueDates;
  }
}
