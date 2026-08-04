import 'package:flutter/material.dart';

import '../models/gps_detection.dart';

/// GPS地区判定で複数候補が見つかった場合のボトムシートを表示する。
///
/// [candidates] の一覧をtownName昇順（Unicode順）で表示し、
/// ユーザーが選択すると確認ダイアログを経由して [DistrictCandidate] を返す。
/// ボトムシート外タップ（dismiss）の場合は null を返す（手動選択モードへ遷移）。
///
/// [overflowMessage] が非nullの場合、リスト上部に注意メッセージを表示する。
Future<DistrictCandidate?> showCandidateBottomSheet({
  required BuildContext context,
  required List<DistrictCandidate> candidates,
  String? overflowMessage,
}) {
  // Sort by townName ascending (Unicode order) for safety, even if already sorted
  final sortedCandidates = List<DistrictCandidate>.from(candidates)
    ..sort((a, b) => a.townName.compareTo(b.townName));

  return showModalBottomSheet<DistrictCandidate?>(
    context: context,
    isDismissible: true,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (bottomSheetContext) {
      return DraggableScrollableSheet(
        initialChildSize: 0.5,
        minChildSize: 0.3,
        maxChildSize: 0.8,
        expand: false,
        builder: (context, scrollController) {
          return Column(
            children: [
              // ハンドルバー
              Container(
                margin: const EdgeInsets.only(top: 12, bottom: 8),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              // タイトル
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Text(
                  '地区候補を選択',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const Divider(),
              // オーバーフローメッセージ
              if (overflowMessage != null)
                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  color: Colors.orange[50],
                  child: Row(
                    children: [
                      Icon(Icons.info_outline,
                          size: 18, color: Colors.orange[700]),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          overflowMessage,
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.orange[800],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              // 候補リスト
              Expanded(
                child: ListView.separated(
                  controller: scrollController,
                  itemCount: sortedCandidates.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final candidate = sortedCandidates[index];
                    return ListTile(
                      title: Text(candidate.districtName),
                      subtitle: Text(candidate.townName),
                      trailing: const Icon(Icons.chevron_right, size: 20),
                      onTap: () async {
                        final confirmed = await _showConfirmationDialog(
                          context: bottomSheetContext,
                          candidate: candidate,
                        );
                        if (confirmed == true && bottomSheetContext.mounted) {
                          Navigator.of(bottomSheetContext).pop(candidate);
                        }
                      },
                    );
                  },
                ),
              ),
            ],
          );
        },
      );
    },
  );
}

/// 地区選択の確認ダイアログを表示する。
///
/// 「{districtName}」に設定しますか？ と表示し、確認/キャンセルを選択させる。
/// 確認時は true を返す。キャンセル時は false を返す（ボトムシートに戻る）。
Future<bool?> _showConfirmationDialog({
  required BuildContext context,
  required DistrictCandidate candidate,
}) {
  return showDialog<bool>(
    context: context,
    builder: (dialogContext) {
      return AlertDialog(
        title: const Text('地区の確認'),
        content: Text('「${candidate.districtName}」に設定しますか？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('キャンセル'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('設定する'),
          ),
        ],
      );
    },
  );
}
