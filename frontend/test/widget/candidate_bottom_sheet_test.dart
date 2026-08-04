import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/widgets/candidate_bottom_sheet.dart';

/// 候補ボトムシートのウィジェットテスト
///
/// Validates: Requirements 1.2, 1.3, 1.4
/// - 候補リストがtownName昇順でボトムシートに表示される
/// - 各項目にdistrictNameとtownNameが表示される
/// - 項目タップで確認ダイアログが表示される
/// - 確認ダイアログで「設定する」を選ぶと候補が返される
/// - ボトムシート外タップでnullが返される
/// - overflowMessageが表示される
void main() {
  final testCandidates = [
    const DistrictCandidate(
      districtNumber: 3,
      districtName: '道後',
      townName: '道後湯之町',
    ),
    const DistrictCandidate(
      districtNumber: 1,
      districtName: '番町',
      townName: '一番町',
    ),
    const DistrictCandidate(
      districtNumber: 5,
      districtName: '清水',
      townName: '清水町',
    ),
  ];

  group('Candidate Bottom Sheet', () {
    testWidgets(
      '候補リストがtownName昇順で表示される',
      (tester) async {
        DistrictCandidate? result;

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      result = await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // ボトムシートが表示されることを確認
        expect(find.text('地区候補を選択'), findsOneWidget);

        // 全候補のtownNameが表示される
        expect(find.text('一番町'), findsOneWidget);
        expect(find.text('清水町'), findsOneWidget);
        expect(find.text('道後湯之町'), findsOneWidget);

        // townName昇順で表示される: 一番町 < 清水町 < 道後湯之町
        final firstTile = tester.getTopLeft(find.text('一番町'));
        final secondTile = tester.getTopLeft(find.text('清水町'));
        final thirdTile = tester.getTopLeft(find.text('道後湯之町'));
        expect(firstTile.dy, lessThan(secondTile.dy));
        expect(secondTile.dy, lessThan(thirdTile.dy));
      },
    );

    testWidgets(
      '各項目にdistrictNameとtownNameが表示される',
      (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // 各候補のdistrictName（title）が表示される
        expect(find.text('番町'), findsOneWidget);
        expect(find.text('清水'), findsOneWidget);
        expect(find.text('道後'), findsOneWidget);

        // 各候補のtownName（subtitle）が表示される
        expect(find.text('一番町'), findsOneWidget);
        expect(find.text('清水町'), findsOneWidget);
        expect(find.text('道後湯之町'), findsOneWidget);
      },
    );

    testWidgets(
      '項目タップで確認ダイアログが表示される',
      (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // 最初の候補（townName昇順で「一番町」= 番町地区）をタップ
        await tester.tap(find.text('一番町'));
        await tester.pumpAndSettle();

        // 確認ダイアログが表示される
        expect(find.text('地区の確認'), findsOneWidget);
        expect(find.text('「番町」に設定しますか？'), findsOneWidget);
        expect(find.text('キャンセル'), findsOneWidget);
        expect(find.text('設定する'), findsOneWidget);
      },
    );

    testWidgets(
      '確認ダイアログで「設定する」を選ぶと候補が返される',
      (tester) async {
        DistrictCandidate? result;

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      result = await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // 「一番町」（番町地区）をタップ
        await tester.tap(find.text('一番町'));
        await tester.pumpAndSettle();

        // 確認ダイアログで「設定する」をタップ
        await tester.tap(find.text('設定する'));
        await tester.pumpAndSettle();

        // 選択した候補が返される
        expect(result, isNotNull);
        expect(result!.districtNumber, 1);
        expect(result!.districtName, '番町');
        expect(result!.townName, '一番町');
      },
    );

    testWidgets(
      '確認ダイアログで「キャンセル」を選ぶとボトムシートに戻る',
      (tester) async {
        DistrictCandidate? result;

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      result = await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // 「一番町」をタップ
        await tester.tap(find.text('一番町'));
        await tester.pumpAndSettle();

        // 確認ダイアログで「キャンセル」をタップ
        await tester.tap(find.text('キャンセル'));
        await tester.pumpAndSettle();

        // ボトムシートがまだ表示されている（候補リストに戻る）
        expect(find.text('地区候補を選択'), findsOneWidget);
        // 結果はまだnull（返されていない）
        expect(result, isNull);
      },
    );

    testWidgets(
      'overflowMessageが指定されている場合に表示される',
      (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                        overflowMessage: '候補が多すぎます。住所を手動で選択してください。',
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // overflowMessageが表示される
        expect(
          find.text('候補が多すぎます。住所を手動で選択してください。'),
          findsOneWidget,
        );
        // 情報アイコンが表示される
        expect(find.byIcon(Icons.info_outline), findsOneWidget);
      },
    );

    testWidgets(
      'overflowMessageが未指定の場合は表示されない',
      (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      await showCandidateBottomSheet(
                        context: context,
                        candidates: testCandidates,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        // ボトムシートを開く
        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        // overflowメッセージ領域がない
        expect(find.byIcon(Icons.info_outline), findsNothing);
      },
    );
  });
}
