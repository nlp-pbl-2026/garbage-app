import 'package:flutter/material.dart';

/// アプリ全体で使用する色定義
///
/// Garbage_Categoryごとに固定の色を割り当て、
/// カレンダーのドット、検索結果一覧、詳細ビューのタグに対して当該色を適用する。
/// すべての画面で同一のGarbage_Categoryに対して同一の色を使用し、
/// 画面間で色の不一致がないようにする。
class AppColors {
  // プライベートコンストラクタ（インスタンス化防止）
  AppColors._();

  // ゴミ分類カテゴリの色定義
  /// 可燃ごみ - ピンク
  static const Color burnable = Color(0xFFE91E63);

  /// 資源ごみ - 緑
  static const Color recyclable = Color(0xFF4CAF50);

  /// プラスチック製容器包装 - オレンジ
  static const Color plastic = Color(0xFFFF9800);

  /// ペットボトル - 青
  static const Color petBottle = Color(0xFF2196F3);

  /// 危険ごみ - 赤
  static const Color hazardous = Color(0xFFF44336);

  // 危険ごみ警告アイコン用
  /// 危険ごみの警告アイコン背景色 - 黄色
  static const Color hazardousWarning = Color(0xFFFFC107);

  // アプリ共通色
  /// アプリのプライマリカラー（ナビゲーションバーのアクティブ状態等）
  static const Color primary = Color(0xFF4CAF50);

  /// エラー表示色
  static const Color error = Color(0xFFF44336);

  /// 注意ボックス背景色
  static const Color cautionBackground = Color(0xFFFFEBEE);

  /// 注意ボックスボーダー色
  static const Color cautionBorder = Color(0xFFF44336);
}
