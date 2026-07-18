import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/app.dart';

void main() {
  testWidgets('アプリが正常に起動する', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: GarbageApp(),
      ),
    );
    await tester.pumpAndSettle();
    // 初回起動時は地域未設定のため、地域選択画面のタイトルが表示される
    expect(find.text('地域を選択'), findsOneWidget);
  });
}
