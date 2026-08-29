import 'package:flutter_riverpod/flutter_riverpod.dart';

/// MainScreen のタブインデックスを表す定数。
///
/// BottomNavigationBar の並び（検索・カレンダー・設定）に対応する。
class MainTab {
  const MainTab._();

  /// 検索タブ
  static const int search = 0;

  /// カレンダータブ
  static const int calendar = 1;

  /// 設定タブ
  static const int settings = 2;
}

/// MainScreen で選択中のタブインデックスを保持する StateProvider。
///
/// MainScreen はこの値を watch して表示タブを決定し、タップ時にこの値を更新する。
/// 通知タップからのナビゲーション（要件 5.1, 5.2）など、UI 外からプログラム的に
/// カレンダータブ（[MainTab.calendar]）へ切り替えるためにも使用する。
/// 初期値は検索タブ（[MainTab.search]）。
final selectedTabProvider = StateProvider<int>((ref) => MainTab.search);
