import 'package:flutter/material.dart';

/// 判別結果オーバーレイウィジェット
///
/// カメラプレビュー上に半透明で表示されるオーバーレイ。
/// 将来的にリアルタイム判別結果を表示するUIの土台として機能する。
/// 現時点ではプレースホルダーテキストを表示する。
///
/// 要件3.1: カメラプレビュー上にオーバーレイとして判別結果プレースホルダーを表示
/// 要件3.2: 「判別結果がここに表示されます」テキストをプレースホルダーとして表示
/// 要件3.3: カメラプレビューの視認性を妨げない半透明デザイン
class ClassificationOverlay extends StatelessWidget {
  const ClassificationOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.bottomCenter,
      child: Container(
        width: double.infinity,
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.25,
        ),
        margin: const EdgeInsets.all(16),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.35),
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Center(
          child: Text(
            '判別結果がここに表示されます',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
