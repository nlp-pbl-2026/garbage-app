import 'package:flutter/material.dart';

import '../models/collection_schedule.dart';
import '../models/garbage_category.dart';

/// カレンダー日付マーカーウィジェット
///
/// 日付に対応する収集スケジュールのカテゴリ色ドットを表示する。
/// 最大5個のドットをRow形式で並べて表示する。
class CalendarDayMarker extends StatelessWidget {
  /// その日の収集スケジュールエントリ一覧
  final List<ScheduleEntry> entries;

  /// ドットのサイズ（デフォルト: 6.0）
  final double dotSize;

  /// ドット間の間隔（デフォルト: 2.0）
  final double dotSpacing;

  const CalendarDayMarker({
    super.key,
    required this.entries,
    this.dotSize = 6.0,
    this.dotSpacing = 2.0,
  });

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return const SizedBox.shrink();
    }

    // カテゴリの重複を排除し、最大5個に制限
    final uniqueCategories = entries
        .map((e) => e.category)
        .toSet()
        .take(5)
        .toList();

    return Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: uniqueCategories.map((category) {
        return Container(
          margin: EdgeInsets.symmetric(horizontal: dotSpacing / 2),
          width: dotSize,
          height: dotSize,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: CategoryColors.getColor(category),
          ),
        );
      }).toList(),
    );
  }
}
