import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/memo_provider.dart';
import '../services/memo_service.dart';

/// メモ入力ダイアログを表示するヘルパー関数
///
/// [date] メモの対象日付
/// [existingMemo] 既存メモのテキスト（編集時）
///
/// 返り値:
/// - true: メモが保存された
/// - false: メモが削除された
/// - null: キャンセルされた
Future<bool?> showMemoDialog({
  required BuildContext context,
  required WidgetRef ref,
  required DateTime date,
  String? existingMemo,
}) async {
  return showDialog<bool?>(
    context: context,
    builder: (dialogContext) => MemoDialog(
      date: date,
      existingMemo: existingMemo,
    ),
  );
}

/// メモ入力ダイアログウィジェット
///
/// テキスト入力フィールド（最大200文字）、文字数カウンター、
/// 保存・キャンセル・削除ボタンを持つダイアログ。
class MemoDialog extends ConsumerStatefulWidget {
  /// メモの対象日付
  final DateTime date;

  /// 既存のメモテキスト（編集時にプリセットする）
  final String? existingMemo;

  const MemoDialog({
    super.key,
    required this.date,
    this.existingMemo,
  });

  @override
  ConsumerState<MemoDialog> createState() => _MemoDialogState();
}

class _MemoDialogState extends ConsumerState<MemoDialog> {
  late final TextEditingController _controller;
  int _currentLength = 0;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.existingMemo ?? '');
    _currentLength = _controller.text.length;
    _controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _controller.removeListener(_onTextChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    setState(() {
      _currentLength = _controller.text.length;
    });
  }

  String get _dialogTitle {
    final month = widget.date.month;
    final day = widget.date.day;
    return '$month/$dayのメモ';
  }

  bool get _isEditing => widget.existingMemo != null;

  Future<void> _onSave() async {
    final text = _controller.text.trim();

    // 空テキストで保存押下時はダイアログを閉じるのみ
    if (text.isEmpty) {
      if (mounted) {
        Navigator.of(context).pop(null);
      }
      return;
    }

    final memoService = ref.read(memoServiceProvider);
    final success = await memoService.saveMemo(widget.date, text);

    if (!mounted) return;

    if (success) {
      Navigator.of(context).pop(true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('メモの保存に失敗しました')),
      );
    }
  }

  Future<void> _onDelete() async {
    // 確認ダイアログを表示
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (confirmContext) => AlertDialog(
        title: const Text('メモの削除'),
        content: const Text('このメモを削除しますか？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(confirmContext).pop(false),
            child: const Text('キャンセル'),
          ),
          TextButton(
            onPressed: () => Navigator.of(confirmContext).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('削除'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    try {
      final memoService = ref.read(memoServiceProvider);
      await memoService.deleteMemo(widget.date);

      if (!mounted) return;
      Navigator.of(context).pop(false);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('メモの削除に失敗しました')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(_dialogTitle),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _controller,
            maxLength: MemoService.maxMemoLength,
            maxLines: 5,
            minLines: 3,
            inputFormatters: [
              LengthLimitingTextInputFormatter(MemoService.maxMemoLength),
            ],
            decoration: const InputDecoration(
              hintText: 'メモを入力...',
              border: OutlineInputBorder(),
              counterText: '', // TextField自体のカウンターは非表示
            ),
          ),
          const SizedBox(height: 4),
          // 文字数カウンター表示
          Align(
            alignment: Alignment.centerRight,
            child: Text(
              '$_currentLength / ${MemoService.maxMemoLength}',
              style: TextStyle(
                fontSize: 12,
                color: _currentLength >= MemoService.maxMemoLength
                    ? Colors.red
                    : Colors.grey[600],
              ),
            ),
          ),
        ],
      ),
      actions: [
        // 削除ボタン: 既存メモ編集時のみ表示
        if (_isEditing)
          TextButton(
            onPressed: _onDelete,
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('削除'),
          ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(null),
          child: const Text('キャンセル'),
        ),
        ElevatedButton(
          onPressed: _onSave,
          child: const Text('保存'),
        ),
      ],
    );
  }
}
