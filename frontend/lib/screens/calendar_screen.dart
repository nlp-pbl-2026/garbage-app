import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:table_calendar/table_calendar.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/collection_schedule.dart';
import '../models/garbage_category.dart';
import '../models/garbage_item.dart';
import '../models/weather.dart';
import '../providers/calendar_provider.dart';
import '../providers/memo_provider.dart';
import '../providers/region_provider.dart';
import '../providers/weather_provider.dart';
import '../services/ical_export_service.dart';
import '../widgets/calendar_day_marker.dart';
import '../widgets/memo_dialog.dart';
import '../widgets/region_header.dart';
import 'region_selection_screen.dart';

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
    final weatherAsync = ref.watch(weatherForecastProvider);
    final memoDates = ref.watch(
      monthlyMemosProvider(DateTime(focusedMonth.year, focusedMonth.month)),
    );

    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: RegionHeader(
        onEditPressed: () => _navigateToRegionSelection(context, ref),
        extraActions: [
          IconButton(
            icon: const Icon(Icons.ios_share, color: Colors.black87),
            onPressed: () => _exportCalendar(context, ref),
            tooltip: 'カレンダーをエクスポート',
          ),
        ],
      ),
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
                      weatherAsync.valueOrNull ?? {},
                      memoDates,
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
                    context,
                    ref,
                    selectedDay,
                    monthlyScheduleAsync,
                    weatherAsync.valueOrNull ?? {},
                  ),

                  // カテゴリ別次回収集日一覧
                  _buildAllCategoriesNextCollection(ref),
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

  /// カテゴリ別次回収集日一覧を構築する
  Widget _buildAllCategoriesNextCollection(WidgetRef ref) {
    final regionAsync = ref.watch(regionSettingProvider);
    final regionSetting = regionAsync.valueOrNull;

    if (regionSetting == null) {
      return const SizedBox.shrink();
    }

    final scheduleService = ref.watch(scheduleServiceProvider);
    final districtId = regionSetting.districtId;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Colors.grey.shade200)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '次回の収集日',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          const SizedBox(height: 8),
          ...GarbageCategory.values.map(
            (category) => _buildCategoryNextDate(
              scheduleService,
              districtId,
              category,
            ),
          ),
        ],
      ),
    );
  }

  /// カテゴリ1件分の次回収集日表示
  Widget _buildCategoryNextDate(
    dynamic scheduleService,
    String districtId,
    GarbageCategory category,
  ) {
    final color = CategoryColors.getColor(category);
    final label = CategoryColors.getLabel(category);

    return FutureBuilder<DateTime?>(
      future: scheduleService.getNextCollectionDate(
        districtId,
        category.toJsonString(),
      ),
      builder: (context, snapshot) {
        String dateText = '---';
        String? daysText;

        if (snapshot.connectionState == ConnectionState.done &&
            snapshot.data != null) {
          final nextDate = snapshot.data!;
          final now = DateTime.now();
          final today = DateTime(now.year, now.month, now.day);
          final diff = nextDate.difference(today).inDays;

          final weekDays = ['月', '火', '水', '木', '金', '土', '日'];
          final weekDay = weekDays[nextDate.weekday - 1];
          dateText = '${nextDate.month}/${nextDate.day}（$weekDay）';

          if (diff == 0) {
            daysText = '今日';
          } else if (diff == 1) {
            daysText = '明日';
          } else {
            daysText = 'あと${diff}日';
          }
        }

        return InkWell(
          onTap: () {
            _showUpcomingScheduleSheet(
              context,
              scheduleService,
              districtId,
              category,
              label,
              color,
            );
          },
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: color,
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 100,
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 13,
                      color: color,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                Expanded(
                  child: Text(
                    dateText,
                    style: const TextStyle(fontSize: 13),
                  ),
                ),
                if (daysText != null)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: daysText == '今日' || daysText == '明日'
                          ? Colors.red.shade50
                          : Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      daysText,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: daysText == '今日' || daysText == '明日'
                            ? Colors.red.shade700
                            : Colors.grey.shade700,
                      ),
                    ),
                  ),
                const SizedBox(width: 4),
                Icon(
                  Icons.chevron_right,
                  size: 16,
                  color: Colors.grey.shade400,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  /// 指定カテゴリの今後の収集日一覧をBottomSheetで表示する
  void _showUpcomingScheduleSheet(
    BuildContext context,
    dynamic scheduleService,
    String districtId,
    GarbageCategory category,
    String label,
    Color color,
  ) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return FutureBuilder<List<DateTime>>(
          future: scheduleService.getUpcomingCollectionDates(
            districtId,
            category.toJsonString(),
          ),
          builder: (context, snapshot) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ハンドル
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 16),
                      decoration: BoxDecoration(
                        color: Colors.grey[300],
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  // タイトル
                  Row(
                    children: [
                      Container(
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: color,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '$labelの収集日',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  // 日程リスト
                  if (snapshot.connectionState == ConnectionState.waiting)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: CircularProgressIndicator(),
                      ),
                    )
                  else if (snapshot.hasData && snapshot.data!.isNotEmpty)
                    ...snapshot.data!.map((date) {
                      final now = DateTime.now();
                      final today = DateTime(now.year, now.month, now.day);
                      final diff = date.difference(today).inDays;
                      final weekDays = ['月', '火', '水', '木', '金', '土', '日'];
                      final weekDay = weekDays[date.weekday - 1];

                      String relative = '';
                      if (diff == 0) {
                        relative = '今日';
                      } else if (diff == 1) {
                        relative = '明日';
                      } else if (diff == 2) {
                        relative = '明後日';
                      }

                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(
                          children: [
                            SizedBox(
                              width: 120,
                              child: Text(
                                '${date.month}/${date.day}（$weekDay）',
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: diff <= 1
                                      ? FontWeight.bold
                                      : FontWeight.normal,
                                ),
                              ),
                            ),
                            if (relative.isNotEmpty)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: diff <= 1
                                      ? Colors.red.shade50
                                      : Colors.orange.shade50,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Text(
                                  relative,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    color: diff <= 1
                                        ? Colors.red.shade700
                                        : Colors.orange.shade700,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      );
                    }),
                  if (snapshot.hasData && snapshot.data!.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(
                        child: Text(
                          '今後の収集日が見つかりません',
                          style: TextStyle(color: Colors.grey),
                        ),
                      ),
                    ),
                  const SizedBox(height: 16),
                ],
              ),
            );
          },
        );
      },
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
    Map<DateTime, DailyWeather> weather,
    Set<DateTime> memoDates,
  ) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.06),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: TableCalendar<ScheduleEntry>(
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
      rowHeight: 64,
      headerStyle: HeaderStyle(
        formatButtonVisible: false,
        titleCentered: true,
        titleTextStyle: const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.bold,
          color: Colors.black87,
        ),
        leftChevronIcon: Icon(Icons.chevron_left, color: AppColors.primary),
        rightChevronIcon: Icon(Icons.chevron_right, color: AppColors.primary),
        headerPadding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.primary.withOpacity(0.05),
          border: Border(
            bottom: BorderSide(color: Colors.grey.shade200),
          ),
        ),
      ),
      daysOfWeekStyle: DaysOfWeekStyle(
        weekdayStyle: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Colors.black54,
        ),
        weekendStyle: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Colors.red.shade400,
        ),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: Colors.grey.shade200),
          ),
        ),
      ),
      calendarStyle: CalendarStyle(
        cellMargin: const EdgeInsets.all(4),
        todayDecoration: BoxDecoration(
          color: AppColors.primary.withOpacity(0.2),
          shape: BoxShape.circle,
          border: Border.all(color: AppColors.primary, width: 2),
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
        defaultBuilder: (context, date, focusedDay) {
          return _buildDayCell(context, ref, date, memoDates, isToday: false, isSelected: false);
        },
        todayBuilder: (context, date, focusedDay) {
          return _buildDayCell(context, ref, date, memoDates, isToday: true, isSelected: false);
        },
        selectedBuilder: (context, date, focusedDay) {
          return _buildDayCell(context, ref, date, memoDates, isToday: false, isSelected: true);
        },
        markerBuilder: (context, date, events) {
          final dateKey = DateTime(date.year, date.month, date.day);
          final entries = schedule[dateKey] ?? [];
          final dailyWeather = weather[dateKey];

          // 天気アイコン + ゴミカテゴリドット
          return Positioned(
            bottom: 1,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (dailyWeather != null)
                  Icon(
                    weatherIcon(dailyWeather.condition),
                    size: 12,
                    color: weatherColor(dailyWeather.condition),
                  ),
                if (entries.isNotEmpty)
                  CalendarDayMarker(entries: entries, dotSize: 5),
              ],
            ),
          );
        },
      ),
      eventLoader: (day) {
        final dateKey = DateTime(day.year, day.month, day.day);
        return schedule[dateKey] ?? [];
      },
    ),
      ),
    );
  }

  /// 日付セルを構築する（長押し対応 + メモインジケーター）
  Widget _buildDayCell(
    BuildContext context,
    WidgetRef ref,
    DateTime date,
    Set<DateTime> memoDates, {
    required bool isToday,
    required bool isSelected,
  }) {
    final dateKey = DateTime(date.year, date.month, date.day);
    final hasMemo = memoDates.contains(dateKey);

    return GestureDetector(
      onLongPress: () => _onDayLongPressed(context, ref, date),
      child: Stack(
        alignment: Alignment.center,
        children: [
          // 日付の背景装飾 + テキスト
          Container(
            margin: const EdgeInsets.all(4),
            decoration: isSelected
                ? const BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                  )
                : isToday
                    ? BoxDecoration(
                        color: AppColors.primary.withOpacity(0.2),
                        shape: BoxShape.circle,
                        border: Border.all(color: AppColors.primary, width: 2),
                      )
                    : null,
            alignment: Alignment.center,
            child: Text(
              '${date.day}',
              style: TextStyle(
                color: isSelected
                    ? Colors.white
                    : isToday
                        ? Colors.black87
                        : date.weekday == DateTime.saturday
                            ? Colors.blue.shade400
                            : date.weekday == DateTime.sunday
                                ? Colors.red.shade400
                                : Colors.black87,
                fontWeight: (isToday || isSelected) ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ),
          // メモインジケーター（右上隅の小さなドット）
          if (hasMemo)
            Positioned(
              top: 4,
              right: 4,
              child: Container(
                width: 4,
                height: 4,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.orange,
                ),
              ),
            ),
        ],
      ),
    );
  }

  /// 日付長押し時にメモダイアログを表示する
  Future<void> _onDayLongPressed(
    BuildContext context,
    WidgetRef ref,
    DateTime date,
  ) async {
    final existingMemo = ref.read(memoForDateProvider(date));

    final result = await showMemoDialog(
      context: context,
      ref: ref,
      date: date,
      existingMemo: existingMemo,
    );

    // メモ保存/削除後にインジケーター状態を更新
    if (result != null) {
      ref.invalidate(monthlyMemosProvider);
    }
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
    BuildContext context,
    WidgetRef ref,
    DateTime? selectedDay,
    AsyncValue<Map<DateTime, List<ScheduleEntry>>> monthlyScheduleAsync,
    Map<DateTime, DailyWeather> weather,
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

    final dateKey = DateTime(
      selectedDay.year,
      selectedDay.month,
      selectedDay.day,
    );
    final dailyWeather = weather[dateKey];

    return monthlyScheduleAsync.when(
      data: (schedule) {
        final entries = schedule[dateKey] ?? [];

        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildDateHeader(selectedDay),
              // 天気情報
              if (dailyWeather != null) ...[
                const SizedBox(height: 12),
                _buildWeatherInfo(dailyWeather),
              ],
              const SizedBox(height: 12),
              if (entries.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8.0),
                  child: Text(
                    AppStrings.noSchedule,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey,
                    ),
                    textAlign: TextAlign.center,
                  ),
                )
              else
                ...entries.map((entry) => _buildScheduleEntryTile(entry)),
              // メモボタン
              const SizedBox(height: 12),
              _buildMemoButton(context, ref, selectedDay),
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

  /// メモ追加/編集ボタンを構築する
  Widget _buildMemoButton(
    BuildContext context,
    WidgetRef ref,
    DateTime date,
  ) {
    final existingMemo = ref.watch(memoForDateProvider(date));
    final hasExistingMemo = existingMemo != null && existingMemo.isNotEmpty;

    return OutlinedButton.icon(
      onPressed: () async {
        final result = await showMemoDialog(
          context: context,
          ref: ref,
          date: date,
          existingMemo: existingMemo,
        );
        if (result != null) {
          ref.invalidate(monthlyMemosProvider);
        }
      },
      icon: Icon(
        hasExistingMemo ? Icons.edit_note : Icons.note_add_outlined,
        size: 18,
      ),
      label: Text(
        hasExistingMemo ? 'メモを編集' : 'メモを追加',
        style: const TextStyle(fontSize: 13),
      ),
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(double.infinity, 36),
      ),
    );
  }

  /// 天気情報ウィジェットを構築する
  Widget _buildWeatherInfo(DailyWeather weather) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.blue.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.blue.withOpacity(0.15)),
      ),
      child: Row(
        children: [
          Icon(
            weatherIcon(weather.condition),
            color: weatherColor(weather.condition),
            size: 28,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  weatherLabel(weather.condition),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${weather.temperatureMax.round()}° / ${weather.temperatureMin.round()}°  '
                  '降水確率 ${weather.precipitationProbability.round()}%',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
        ],
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

  /// カレンダーをiCal形式でエクスポートし共有する
  Future<void> _exportCalendar(BuildContext context, WidgetRef ref) async {
    final regionAsync = ref.read(regionSettingProvider);
    final regionSetting = regionAsync.valueOrNull;

    if (regionSetting == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('地域が設定されていません')),
        );
      }
      return;
    }

    // ローディング表示
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 16),
                Text('エクスポート中...'),
              ],
            ),
          ),
        ),
      ),
    );

    try {
      final scheduleService = ref.read(scheduleServiceProvider);
      final exportService = IcalExportService(scheduleService);
      await exportService.exportAndShare(regionSetting.districtId);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('エクスポートに失敗しました: $e')),
        );
      }
    } finally {
      // ローディングダイアログを閉じる
      if (context.mounted) {
        Navigator.of(context).pop();
      }
    }
  }

  /// 地域選択画面へ遷移する
  void _navigateToRegionSelection(BuildContext context, WidgetRef ref) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => RegionSelectionScreen(
          onRegionSelected: () {
            Navigator.of(context).pop();
          },
        ),
      ),
    );
  }
}
