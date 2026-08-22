import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../models/bulky_waste.dart';
import '../../providers/bulky_waste_provider.dart';

/// 粗大ごみ申し込み状況追跡ウィジェット
///
/// ローカルに保存された申し込み記録を管理する画面。
/// 記録の新規作成、ステータス変更、完了アーカイブ、期限超過表示を提供する。
///
/// 要件7.1: 品目名（最大50文字）・収集予定日（今日以降）・ステータスで記録作成
/// 要件7.2: applied / ticketPurchased / awaitingCollection を任意順序で変更可能
/// 要件7.3: ステータス更新をローカルに永続化
/// 要件7.5: completed設定時にアーカイブリストへ移動
/// 要件7.6: 品目名空/過去日付のバリデーション
/// 要件7.7: 収集日超過の未完了レコードに「期限超過」表示
class StatusTrackerView extends ConsumerWidget {
  const StatusTrackerView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(applicationRecordsProvider.notifier);
    final records = ref.watch(applicationRecordsProvider);

    final activeRecords =
        records.where((r) => r.status != ApplicationStatus.completed).toList();
    final archivedRecords =
        records.where((r) => r.status == ApplicationStatus.completed).toList();

    return Stack(
      children: [
        activeRecords.isEmpty && archivedRecords.isEmpty
            ? _EmptyState(onAdd: () => _showAddRecordDialog(context, notifier))
            : _RecordListBody(
                activeRecords: activeRecords,
                archivedRecords: archivedRecords,
                notifier: notifier,
              ),
        Positioned(
          right: 16,
          bottom: 16,
          child: FloatingActionButton.extended(
            onPressed: () => _showAddRecordDialog(context, notifier),
            icon: const Icon(Icons.add),
            label: const Text('新規登録'),
          ),
        ),
      ],
    );
  }

  /// 記録追加ダイアログを表示する
  void _showAddRecordDialog(
    BuildContext context,
    ApplicationRecordNotifier notifier,
  ) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => _AddRecordSheet(notifier: notifier),
    );
  }
}

/// 記録が空のときの表示
class _EmptyState extends StatelessWidget {
  final VoidCallback onAdd;

  const _EmptyState({required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.assignment_outlined,
            size: 64,
            color: Colors.grey[400],
          ),
          const SizedBox(height: 16),
          Text(
            '申し込み記録がありません',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.grey[600],
                ),
          ),
          const SizedBox(height: 8),
          Text(
            '「新規登録」ボタンから記録を追加できます',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey[500],
                ),
          ),
        ],
      ),
    );
  }
}

/// アクティブ記録 + アーカイブセクションを表示するボディ
class _RecordListBody extends StatelessWidget {
  final List<ApplicationRecord> activeRecords;
  final List<ApplicationRecord> archivedRecords;
  final ApplicationRecordNotifier notifier;

  const _RecordListBody({
    required this.activeRecords,
    required this.archivedRecords,
    required this.notifier,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: 80,
      ),
      children: [
        // アクティブ記録セクション
        if (activeRecords.isNotEmpty) ...[
          Text(
            '進行中の申し込み',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 8),
          ...activeRecords.map(
            (record) => _ActiveRecordCard(
              record: record,
              notifier: notifier,
              locale: Localizations.localeOf(context).languageCode,
            ),
          ),
        ],
        // アーカイブセクション
        if (archivedRecords.isNotEmpty) ...[
          const SizedBox(height: 24),
          _ArchivedSection(
            archivedRecords: archivedRecords,
            locale: Localizations.localeOf(context).languageCode,
          ),
        ],
      ],
    );
  }
}

/// アクティブ記録カード
///
/// ステータスバッジ、期限超過バッジ、ステータス変更メニュー、完了ボタンを含む。
class _ActiveRecordCard extends StatelessWidget {
  final ApplicationRecord record;
  final ApplicationRecordNotifier notifier;
  final String locale;

  const _ActiveRecordCard({
    required this.record,
    required this.notifier,
    required this.locale,
  });

  /// 収集日が過去かどうか判定する
  bool get _isOverdue {
    final today = DateTime.now();
    final todayDateOnly = DateTime(today.year, today.month, today.day);
    final collectionDateOnly = DateTime(
      record.collectionDate.year,
      record.collectionDate.month,
      record.collectionDate.day,
    );
    return collectionDateOnly.isBefore(todayDateOnly);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ヘッダー行：品目名 + バッジ
            Row(
              children: [
                Expanded(
                  child: Text(
                    record.itemName,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                _StatusBadge(status: record.status),
                if (_isOverdue) ...[
                  const SizedBox(width: 6),
                  _OverdueBadge(),
                ],
              ],
            ),
            const SizedBox(height: 8),
            // 収集予定日
            Row(
              children: [
                Icon(
                  Icons.calendar_today,
                  size: 16,
                  color: _isOverdue ? Colors.red[700] : Colors.grey[600],
                ),
                const SizedBox(width: 4),
                Text(
                  '収集予定日: ${_formatDate(record.collectionDate)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: _isOverdue ? Colors.red[700] : Colors.grey[600],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // アクション行：ステータス変更 + 完了ボタン
            Row(
              children: [
                Expanded(
                  child: _StatusDropdown(
                    currentStatus: record.status,
                    onChanged: (newStatus) {
                      notifier.updateStatus(record.id, newStatus);
                    },
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => notifier.archiveRecord(record.id),
                  icon: const Icon(Icons.check_circle_outline, size: 18),
                  label: const Text('完了'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.green[700],
                    side: BorderSide(color: Colors.green[300]!),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    return DateFormat.yMd(locale).format(date);
  }
}

/// ステータスバッジ
///
/// applied=青、ticketPurchased=橙、awaitingCollection=緑で表示する。
class _StatusBadge extends StatelessWidget {
  final ApplicationStatus status;

  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final (label, color) = _statusInfo(status);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: color,
        ),
      ),
    );
  }

  (String, Color) _statusInfo(ApplicationStatus status) {
    switch (status) {
      case ApplicationStatus.applied:
        return ('申し込み済', Colors.blue);
      case ApplicationStatus.ticketPurchased:
        return ('処理券購入済', Colors.orange);
      case ApplicationStatus.awaitingCollection:
        return ('収集待ち', Colors.green);
      case ApplicationStatus.completed:
        return ('完了', Colors.grey);
    }
  }
}

/// 期限超過バッジ
class _OverdueBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.red.withValues(alpha: 0.5)),
      ),
      child: const Text(
        '期限超過',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.bold,
          color: Colors.red,
        ),
      ),
    );
  }
}

/// ステータス変更ドロップダウン
///
/// applied / ticketPurchased / awaitingCollection を任意順序で変更可能。
class _StatusDropdown extends StatelessWidget {
  final ApplicationStatus currentStatus;
  final ValueChanged<ApplicationStatus> onChanged;

  const _StatusDropdown({
    required this.currentStatus,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    // completed以外の選択肢
    const availableStatuses = [
      ApplicationStatus.applied,
      ApplicationStatus.ticketPurchased,
      ApplicationStatus.awaitingCollection,
    ];

    return DropdownButtonFormField<ApplicationStatus>(
      value: currentStatus,
      decoration: InputDecoration(
        labelText: 'ステータス',
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 8,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        isDense: true,
      ),
      items: availableStatuses.map((status) {
        final (label, _) = _statusLabel(status);
        return DropdownMenuItem(
          value: status,
          child: Text(label, style: const TextStyle(fontSize: 13)),
        );
      }).toList(),
      onChanged: (value) {
        if (value != null && value != currentStatus) {
          onChanged(value);
        }
      },
    );
  }

  (String, Color) _statusLabel(ApplicationStatus status) {
    switch (status) {
      case ApplicationStatus.applied:
        return ('申し込み済', Colors.blue);
      case ApplicationStatus.ticketPurchased:
        return ('処理券購入済', Colors.orange);
      case ApplicationStatus.awaitingCollection:
        return ('収集待ち', Colors.green);
      case ApplicationStatus.completed:
        return ('完了', Colors.grey);
    }
  }
}

/// アーカイブセクション（折りたたみ可能）
class _ArchivedSection extends StatelessWidget {
  final List<ApplicationRecord> archivedRecords;
  final String locale;

  const _ArchivedSection({required this.archivedRecords, required this.locale});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ExpansionTile(
      initiallyExpanded: false,
      tilePadding: EdgeInsets.zero,
      title: Row(
        children: [
          Icon(Icons.archive_outlined, size: 20, color: Colors.grey[600]),
          const SizedBox(width: 8),
          Text(
            '完了済み (${archivedRecords.length}件)',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.grey[700],
            ),
          ),
        ],
      ),
      children: archivedRecords
          .map((record) => _ArchivedRecordTile(record: record, locale: locale))
          .toList(),
    );
  }
}

/// アーカイブ済み記録タイル
class _ArchivedRecordTile extends StatelessWidget {
  final ApplicationRecord record;
  final String locale;

  const _ArchivedRecordTile({required this.record, required this.locale});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 8),
      leading: Icon(
        Icons.check_circle,
        color: Colors.green[400],
        size: 24,
      ),
      title: Text(
        record.itemName,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: Colors.grey[700],
        ),
      ),
      subtitle: Text(
        '収集日: ${_formatDate(record.collectionDate)}',
        style: theme.textTheme.bodySmall?.copyWith(
          color: Colors.grey[500],
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    return DateFormat.yMd(locale).format(date);
  }
}

/// 記録追加用ボトムシート
///
/// 品目名（最大50文字）と収集予定日（今日以降）を入力し、記録を作成する。
class _AddRecordSheet extends StatefulWidget {
  final ApplicationRecordNotifier notifier;

  const _AddRecordSheet({required this.notifier});

  @override
  State<_AddRecordSheet> createState() => _AddRecordSheetState();
}

class _AddRecordSheetState extends State<_AddRecordSheet> {
  final _formKey = GlobalKey<FormState>();
  final _itemNameController = TextEditingController();
  DateTime? _selectedDate;
  String? _dateError;
  bool _isSubmitting = false;

  @override
  void dispose() {
    _itemNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Padding(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: bottomInset + 24,
      ),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // タイトル
            Text(
              '新規申し込み記録',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            // 品目名テキストフィールド
            TextFormField(
              controller: _itemNameController,
              maxLength: 50,
              decoration: const InputDecoration(
                labelText: '品目名',
                hintText: '例: ソファー、自転車',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.inventory_2_outlined),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return '品目名を入力してください';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),
            // 収集予定日ピッカー
            _DatePickerField(
              selectedDate: _selectedDate,
              error: _dateError,
              onDateSelected: (date) {
                setState(() {
                  _selectedDate = date;
                  _dateError = null;
                });
              },
            ),
            const SizedBox(height: 24),
            // 送信ボタン
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _isSubmitting ? null : _submit,
                child: _isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('登録する'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    // 日付バリデーション
    if (_selectedDate == null) {
      setState(() {
        _dateError = '収集予定日を選択してください';
      });
    }

    final isFormValid = _formKey.currentState!.validate();
    if (!isFormValid || _selectedDate == null) {
      return;
    }

    setState(() => _isSubmitting = true);

    final error = await widget.notifier.addRecord(
      itemName: _itemNameController.text,
      collectionDate: _selectedDate!,
    );

    if (!mounted) return;

    if (error != null) {
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error),
          backgroundColor: Colors.red,
        ),
      );
    } else {
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('記録を追加しました'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }
}

/// 日付選択フィールド
///
/// タップで日付ピッカーを表示する。firstDateは今日に設定。
class _DatePickerField extends StatelessWidget {
  final DateTime? selectedDate;
  final String? error;
  final ValueChanged<DateTime> onDateSelected;

  const _DatePickerField({
    required this.selectedDate,
    required this.error,
    required this.onDateSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => _pickDate(context),
          borderRadius: BorderRadius.circular(4),
          child: InputDecorator(
            decoration: InputDecoration(
              labelText: '収集予定日',
              border: const OutlineInputBorder(),
              prefixIcon: const Icon(Icons.calendar_today),
              errorText: error,
            ),
            child: Text(
              selectedDate != null
                  ? DateFormat.yMd(Localizations.localeOf(context).languageCode)
                      .format(selectedDate!)
                  : '日付を選択',
              style: TextStyle(
                color: selectedDate != null ? null : Colors.grey[600],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _pickDate(BuildContext context) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    final picked = await showDatePicker(
      context: context,
      initialDate: selectedDate ?? today,
      firstDate: today,
      lastDate: today.add(const Duration(days: 365)),
      locale: Localizations.localeOf(context),
    );

    if (picked != null) {
      onDateSelected(picked);
    }
  }
}
