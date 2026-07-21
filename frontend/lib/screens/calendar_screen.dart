import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/collection_schedule.dart';
import '../models/garbage_category.dart';
import '../models/garbage_item.dart';
import '../providers/calendar_provider.dart';
import '../widgets/calendar_day_marker.dart';
import '../widgets/region_header.dart';

/// カレンダー画面
///
/// table_calendarを使用した月間収集スケジュール表示。
/// 各日付にカテゴリ色ドットインジケーターを表示し、
/// 日付選択で当日の収集予定を表示する。
/// 上部バナーに次回収集予定を表示する。
class CalendarScreen extends ConsumerWidget {
  const CalendarScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final focusedMonth = ref.watch(focusedMonthProvider);
    final selectedDay = ref.watch(selectedDayProvider);
    final monthlyScheduleAsync = ref.watch(
      monthlyScheduleProvider(DateTime(focusedMonth.year, focusedMonth.month)),
    );
    final nextCollectionAsync = ref.watch(nextCollectionProvider);

    return Scaffold(
      appBar: const RegionHeader(),
      body: Column(
        children: [
          // 次回収集予定バナー
          _buildNextCollectionBanner(nextCollectionAsync),

          // カレンダー本体
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  monthlyScheduleAsync.when(
                    data: (schedule) => _buildCalendar(
                      context,
                      ref,
                      focusedMonth,
                      selectedDay,
                      schedule,
                    ),
                    loading: () => const Padding(
                      padding: EdgeInsets.all(32.0),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                    error: (_, __) => Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Text(
                        AppStrings.dataLoadError,
                        style: TextStyle(color: AppColors.error),
                      ),
                    ),
                  ),

                  // 色凡例
                  _buildColorLegend(),

                  const Divider(height: 1),

                  // 選択日の収集予定表示
                  _buildSelectedDaySchedule(
                    selectedDay,
                    monthlyScheduleAsync,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 次回収集予定バナーを構築する
  Widget _buildNextCollectionBanner(
    AsyncValue<ScheduleEntry?> nextCollectionAsync,
  ) {
    return nextCollectionAsync.when(
      data: (entry) {
        if (entry == null) {
          return const SizedBox.shrink();
        }
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          color: AppColors.primary.withOpacity(0.9),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                AppStrings.nextCollection,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '${_formatNextCollectionDate(entry.date)} ${CategoryColors.getLabel(entry.category)}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        );
      },
      loading: () => Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        color: AppColors.primary.withOpacity(0.9),
        child: const Center(
          child: SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: Colors.white,
            ),
          ),
        ),
      ),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  /// 次回収集日のフォーマット（「明日」「明後日」「M/d」）
  String _formatNextCollectionDate(DateTime date) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final targetDate = DateTime(date.year, date.month, date.day);
    final difference = targetDate.difference(today).inDays;

    if (difference == 0) {
      return '今日 ${date.month}/${date.day}';
    } else if (difference == 1) {
      return '明日 ${date.month}/${date.day}';
    } else if (difference == 2) {
      return '明後日 ${date.month}/${date.day}';
    } else {
      return '${date.month}/${date.day}';
    }
  }

  /// カレンダーウィジェットを構築する
  Widget _buildCalendar(
    BuildContext context,
    WidgetRef ref,
    DateTime focusedMonth,
    DateTime? selectedDay,
    Map<DateTime, List<ScheduleEntry>> schedule,
  ) {
    return TableCalendar<ScheduleEntry>(
      firstDay: DateTime(2024, 1, 1),
      lastDay: DateTime(2026, 12, 31),
      focusedDay: focusedMonth,
      selectedDayPredicate: (day) {
        if (selectedDay == null) return false;
        return isSameDay(day, selectedDay);
      },
      onDaySelected: (selected, focused) {
        ref.read(selectedDayProvider.notifier).state = selected;
        ref.read(focusedMonthProvider.notifier).state = focused;
      },
      onPageChanged: (focusedDay) {
        ref.read(focusedMonthProvider.notifier).state = focusedDay;
      },
      locale: 'ja_JP',
      startingDayOfWeek: StartingDayOfWeek.sunday,
      headerStyle: const HeaderStyle(
        formatButtonVisible: false,
        titleCentered: true,
        titleTextStyle: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
        ),
      ),
      calendarStyle: CalendarStyle(
        todayDecoration: BoxDecoration(
          color: AppColors.primary.withOpacity(0.3),
          shape: BoxShape.circle,
        ),
        todayTextStyle: const TextStyle(
          color: Colors.black87,
          fontWeight: FontWeight.bold,
        ),
        selectedDecoration: const BoxDecoration(
          color: AppColors.primary,
          shape: BoxShape.circle,
        ),
        selectedTextStyle: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.bold,
        ),
        outsideDaysVisible: false,
      ),
      calendarBuilders: CalendarBuilders<ScheduleEntry>(
        markerBuilder: (context, date, events) {
          final dateKey = DateTime(date.year, date.month, date.day);
          final entries = schedule[dateKey] ?? [];
          if (entries.isEmpty) return null;

          return Positioned(
            bottom: 1,
            child: CalendarDayMarker(entries: entries),
          );
        },
      ),
      eventLoader: (day) {
        final dateKey = DateTime(day.year, day.month, day.day);
        return schedule[dateKey] ?? [];
      },
    );
  }

  /// 色凡例を構築する
  Widget _buildColorLegend() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: GarbageCategory.values.map((category) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: CategoryColors.getColor(category),
                ),
              ),
              const SizedBox(width: 4),
              Text(
                _getShortLabel(category),
                style: const TextStyle(fontSize: 11),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  /// カテゴリの短縮ラベルを取得する
  String _getShortLabel(GarbageCategory category) {
    switch (category) {
      case GarbageCategory.burnable:
        return '可燃';
      case GarbageCategory.recyclable:
        return '資源';
      case GarbageCategory.plastic:
        return 'プラ';
      case GarbageCategory.petBottle:
        return 'ペット';
      case GarbageCategory.hazardous:
        return '危険';
    }
  }

  /// 選択日の収集予定を表示する
  Widget _buildSelectedDaySchedule(
    DateTime? selectedDay,
    AsyncValue<Map<DateTime, List<ScheduleEntry>>> monthlyScheduleAsync,
  ) {
    if (selectedDay == null) {
      return const Padding(
        padding: EdgeInsets.all(24.0),
        child: Text(
          '日付を選択してください',
          style: TextStyle(
            fontSize: 14,
            color: Colors.grey,
          ),
          textAlign: TextAlign.center,
        ),
      );
    }

    return monthlyScheduleAsync.when(
      data: (schedule) {
        final dateKey = DateTime(
          selectedDay.year,
          selectedDay.month,
          selectedDay.day,
        );
        final entries = schedule[dateKey] ?? [];

        if (entries.isEmpty) {
          return Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              children: [
                _buildDateHeader(selectedDay),
                const SizedBox(height: 16),
                const Text(
                  AppStrings.noSchedule,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          );
        }

        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildDateHeader(selectedDay),
              const SizedBox(height: 12),
              ...entries.map((entry) => _buildScheduleEntryTile(entry)),
            ],
          ),
        );
      },
      loading: () => const Padding(
        padding: EdgeInsets.all(24.0),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (_, __) => const Padding(
        padding: EdgeInsets.all(24.0),
        child: Text(
          AppStrings.dataLoadError,
          style: TextStyle(color: AppColors.error),
        ),
      ),
    );
  }

  /// 選択日の日付ヘッダーを構築する
  Widget _buildDateHeader(DateTime date) {
    final weekDays = ['月', '火', '水', '木', '金', '土', '日'];
    final weekDay = weekDays[date.weekday - 1];

    return Text(
      '${date.month}月${date.day}日（$weekDay）の収集',
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  /// 収集予定エントリのタイルを構築する
  Widget _buildScheduleEntryTile(ScheduleEntry entry) {
    final color = CategoryColors.getColor(entry.category);
    final label = CategoryColors.getLabel(entry.category);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              _getCategoryIcon(entry.category),
              color: color,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// カテゴリに対応するアイコンを取得する
  IconData _getCategoryIcon(GarbageCategory category) {
    switch (category) {
      case GarbageCategory.burnable:
        return Icons.local_fire_department;
      case GarbageCategory.recyclable:
        return Icons.recycling;
      case GarbageCategory.plastic:
        return Icons.shopping_bag_outlined;
      case GarbageCategory.petBottle:
        return Icons.water_drop_outlined;
      case GarbageCategory.hazardous:
        return Icons.warning_amber;
    }
  }
}
