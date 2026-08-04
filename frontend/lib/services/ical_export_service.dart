import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../models/collection_schedule.dart';
import '../models/garbage_category.dart';
import '../models/garbage_item.dart';
import 'schedule_service.dart';

/// iCal (.ics) 形式でゴミ収集スケジュールをエクスポートするサービス
///
/// 指定地区の今後のスケジュールをiCalendar形式に変換し、
/// 共有シートを通じて外部カレンダーアプリへ連携する機能を提供する。
/// Web環境ではテキスト共有、ネイティブ環境ではファイル共有を使い分ける。
class IcalExportService {
  final ScheduleService _scheduleService;

  IcalExportService(this._scheduleService);

  /// 指定地区の今後[months]ヶ月分のスケジュールをiCal形式の文字列に変換する
  Future<String> generateIcalString(
    String districtId, {
    int months = 3,
  }) async {
    final now = DateTime.now();
    final buffer = StringBuffer();

    buffer.writeln('BEGIN:VCALENDAR');
    buffer.writeln('VERSION:2.0');
    buffer.writeln('PRODID:-//GarbageApp//JP');
    buffer.writeln('CALSCALE:GREGORIAN');
    buffer.writeln('METHOD:PUBLISH');
    buffer.writeln('X-WR-CALNAME:ゴミ収集カレンダー');

    for (int i = 0; i < months; i++) {
      final targetMonth = DateTime(now.year, now.month + i, 1);
      final schedule = await _scheduleService.getMonthlySchedule(
        districtId,
        targetMonth.year,
        targetMonth.month,
      );

      for (final entry in schedule.entries) {
        for (final scheduleEntry in entry.value) {
          _writeVEvent(buffer, scheduleEntry);
        }
      }
    }

    buffer.writeln('END:VCALENDAR');
    return buffer.toString();
  }

  void _writeVEvent(StringBuffer buffer, ScheduleEntry entry) {
    final label = CategoryColors.getLabel(entry.category);
    final dateStr = _formatDate(entry.date);
    final uid = '${dateStr}-${entry.category.toJsonString()}@garbageapp';

    buffer.writeln('BEGIN:VEVENT');
    buffer.writeln('DTSTART;VALUE=DATE:$dateStr');
    buffer.writeln('SUMMARY:${label}の日');
    buffer.writeln('DESCRIPTION:今日は${label}の収集日です');
    buffer.writeln('UID:$uid');
    buffer.writeln('END:VEVENT');
  }

  String _formatDate(DateTime date) {
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '$year$month$day';
  }

  /// iCalデータを共有する
  ///
  /// Web環境: テキストとして共有（Share.share）
  /// ネイティブ環境: テンポラリファイルに書き出してファイル共有
  Future<void> exportAndShare(String districtId, {int months = 3}) async {
    final icalString = await generateIcalString(districtId, months: months);

    if (kIsWeb) {
      // Web環境ではテキスト共有を使用（path_providerが使えないため）
      await Share.share(
        icalString,
        subject: 'ゴミ収集カレンダー',
      );
    } else {
      // ネイティブ環境ではファイル共有を使用
      final tempDir = await getTemporaryDirectory();
      final file = File('${tempDir.path}/garbage_schedule.ics');
      await file.writeAsString(icalString);

      await Share.shareXFiles(
        [XFile(file.path, mimeType: 'text/calendar')],
        subject: 'ゴミ収集カレンダー',
      );
    }
  }
}
