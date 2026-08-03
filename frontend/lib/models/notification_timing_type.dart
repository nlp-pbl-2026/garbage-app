/// 通知タイミング種別
///
/// ゴミ出し通知のタイミングを表す列挙型。
/// 各カテゴリに対してタイミングごとにON/OFFを設定できる。
enum NotificationTimingType {
  /// 前日通知（夕方）
  evening,

  /// 当日通知（朝）
  morning,
}
