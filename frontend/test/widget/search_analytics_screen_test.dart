import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/screens/search_analytics_screen.dart';
import 'package:garbage_app/services/search_analytics_service.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('admin can expand research dialogue and a rejected key clears it',
      (tester) async {
    tester.view.physicalSize = const Size(1100, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var calls = 0;
    final service = SearchAnalyticsService(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        calls++;
        if (request.headers['X-Analytics-Key'] != 'test-admin-key') {
          return http.Response(
            jsonEncode({'detail': '分析キーが正しくありません。'}),
            403,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }
        return http.Response(
            jsonEncode({
              'total_searches': 1,
              'answered_count': 1,
              'average_duration_ms': 1200,
              'categories': {'ペットボトル': 1},
              'recent': [
                {
                  'query': '洗ったPETボトル本体',
                  'rewritten_query': '飲料用ペットボトル本体',
                  'clarifications': [
                    {'question': 'ラベルは外しましたか？', 'answer': '外しました'}
                  ],
                  'answer': 'ペットボトルの収集日に出してください。',
                  'status': 'answered',
                  'category_name': 'ペットボトル',
                  'confidence': 0.97,
                  'duration_ms': 1200,
                  'created_at': '2026-11-15T00:00:00Z',
                },
                {
                  'query': '容器を捨てたい',
                  'status': 'needs_clarification',
                  'follow_up_question': '容器の素材は何ですか？',
                }
              ],
            }),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'});
      }),
    );
    await tester
        .pumpWidget(MaterialApp(home: SearchAnalyticsScreen(service: service)));
    expect(calls, 0);
    expect(find.text('洗ったPETボトル本体'), findsNothing);
    await tester.enterText(find.byType(TextField), 'test-admin-key');
    await tester.tap(find.text('表示'));
    await tester.pumpAndSettle();
    expect(calls, 1);
    await tester.tap(find.text('洗ったPETボトル本体'));
    await tester.pumpAndSettle();
    expect(find.text('飲料用ペットボトル本体'), findsOneWidget);
    expect(find.text('ラベルは外しましたか？'), findsOneWidget);
    expect(find.text('外しました'), findsOneWidget);
    expect(find.text('ペットボトルの収集日に出してください。'), findsOneWidget);
    await tester.ensureVisible(find.text('容器を捨てたい'));
    await tester.tap(find.text('容器を捨てたい'));
    await tester.pumpAndSettle();
    expect(find.text('容器の素材は何ですか？'), findsOneWidget);
    await tester.ensureVisible(find.byType(TextField));
    await tester.enterText(find.byType(TextField), 'wrong-key');
    await tester.tap(find.text('表示'));
    await tester.pumpAndSettle();
    expect(find.text('分析キーが正しくありません。'), findsOneWidget);
    expect(find.text('洗ったPETボトル本体'), findsNothing);
    expect(find.text('ペットボトルの収集日に出してください。'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
