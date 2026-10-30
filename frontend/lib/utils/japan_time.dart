/// Japan has a fixed UTC+09:00 offset; use its wall date for collection days.
DateTime japanWallTime(DateTime instant) {
  final jst = instant.toUtc().add(const Duration(hours: 9));
  return DateTime(jst.year, jst.month, jst.day, jst.hour, jst.minute,
      jst.second, jst.millisecond, jst.microsecond);
}
