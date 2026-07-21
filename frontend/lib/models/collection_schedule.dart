/// 収集スケジュールのデータモデル
///
/// CollectionRuleは収集ルール（曜日ベース）を定義し、
/// ScheduleEntryは特定日付の収集予定を表す。

import 'garbage_item.dart';

/// 収集スケジュールエントリ
///
/// 特定日付における特定地区・カテゴリの収集予定を表す。
class ScheduleEntry {
  final String districtId;
  final GarbageCategory category;
  final DateTime date;

  ScheduleEntry({
    required this.districtId,
    required this.category,
    required this.date,
  });

  factory ScheduleEntry.fromJson(Map<String, dynamic> json) {
    return ScheduleEntry(
      districtId: json['districtId'] as String,
      category:
          GarbageCategoryExtension.fromString(json['category'] as String),
      date: DateTime.parse(json['date'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'districtId': districtId,
      'category': category.toJsonString(),
      'date': date.toIso8601String(),
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ScheduleEntry &&
          runtimeType == other.runtimeType &&
          districtId == other.districtId &&
          category == other.category &&
          date.year == other.date.year &&
          date.month == other.date.month &&
          date.day == other.date.day;

  @override
  int get hashCode =>
      districtId.hashCode ^
      category.hashCode ^
      date.year.hashCode ^
      date.month.hashCode ^
      date.day.hashCode;

  @override
  String toString() =>
      'ScheduleEntry(districtId: $districtId, category: $category, date: $date)';
}

/// 収集ルール（曜日ベース）
///
/// JSONデータから読み込まれる収集ルールを表す。
/// dayOfWeekは収集曜日（1=月曜, 7=日曜、Dart DateTime.weekdayと同じ）
/// weekOfMonthはnull=毎週、1-4=第n週
class CollectionRule {
  final String districtId;
  final GarbageCategory category;
  final List<int> dayOfWeek;
  final int? weekOfMonth;

  CollectionRule({
    required this.districtId,
    required this.category,
    required this.dayOfWeek,
    this.weekOfMonth,
  });

  factory CollectionRule.fromJson(Map<String, dynamic> json) {
    return CollectionRule(
      districtId: json['districtId'] as String,
      category:
          GarbageCategoryExtension.fromString(json['category'] as String),
      dayOfWeek: (json['dayOfWeek'] as List<dynamic>)
          .map((e) => e as int)
          .toList(),
      weekOfMonth: json['weekOfMonth'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'districtId': districtId,
      'category': category.toJsonString(),
      'dayOfWeek': dayOfWeek,
      'weekOfMonth': weekOfMonth,
    };
  }

  /// 指定月のスケジュール日付リストを生成
  ///
  /// [year] 年、[month] 月に属する収集日をリストとして返す。
  /// dayOfWeekで指定された曜日のうち、weekOfMonthが指定されている場合は
  /// 該当する第n週の日付のみを含む。weekOfMonthがnullの場合は毎週の日付を含む。
  List<DateTime> generateDatesForMonth(int year, int month) {
    final dates = <DateTime>[];

    // 指定月の日数を取得
    final daysInMonth = DateTime(year, month + 1, 0).day;

    for (int day = 1; day <= daysInMonth; day++) {
      final date = DateTime(year, month, day);
      final weekday = date.weekday; // 1=月曜, 7=日曜

      // 指定された曜日に該当するか確認
      if (dayOfWeek.contains(weekday)) {
        if (weekOfMonth == null) {
          // 毎週：すべての該当曜日を追加
          dates.add(date);
        } else {
          // 第n週：該当する週の日付のみ追加
          final weekNumber = _getWeekOfMonth(day);
          if (weekNumber == weekOfMonth) {
            dates.add(date);
          }
        }
      }
    }

    return dates;
  }

  /// 日付から第何週かを計算する
  ///
  /// 第1週=1日〜7日、第2週=8日〜14日、第3週=15日〜21日、第4週=22日〜28日、第5週=29日以降
  int _getWeekOfMonth(int day) {
    return ((day - 1) ~/ 7) + 1;
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CollectionRule &&
          runtimeType == other.runtimeType &&
          districtId == other.districtId &&
          category == other.category;

  @override
  int get hashCode => districtId.hashCode ^ category.hashCode;

  @override
  String toString() =>
      'CollectionRule(districtId: $districtId, category: $category, '
      'dayOfWeek: $dayOfWeek, weekOfMonth: $weekOfMonth)';
}
