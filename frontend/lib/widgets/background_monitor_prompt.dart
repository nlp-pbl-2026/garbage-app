import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/background_monitor_state.dart';
import '../providers/background_location_monitor.dart';
import '../providers/gps_detection_provider.dart';
import '../screens/region_selection_screen.dart';

/// バックグラウンド位置監視のプロンプト表示を管理するウィジェット。
///
/// [BackgroundMonitorPrompting] 状態を検出した場合に、地域設定の更新を促す
/// ダイアログを表示する。childウィジェットをラップして使用する。
///
/// - 「更新する」: GPS地区判定フローを開始。失敗時はエラー表示+手動遷移オプション。
/// - 「後で」: 24時間のクールダウンを設定。
/// - 暗黙的な閉じ（戻るボタン、バックグラウンド移行）: 「後で」と同等。
class BackgroundMonitorPrompt extends ConsumerStatefulWidget {
  final Widget child;

  const BackgroundMonitorPrompt({super.key, required this.child});

  @override
  ConsumerState<BackgroundMonitorPrompt> createState() =>
      _BackgroundMonitorPromptState();
}

class _BackgroundMonitorPromptState
    extends ConsumerState<BackgroundMonitorPrompt> with WidgetsBindingObserver {
  bool _isDialogShowing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // アプリがバックグラウンドに移行した場合、ダイアログ表示中なら暗黙的にdismiss
    if (state == AppLifecycleState.paused && _isDialogShowing) {
      _dismissImplicitly();
    }
  }

  /// 暗黙的なdismiss（戻るボタン、バックグラウンド移行）時の処理。
  /// 「後で」と同等の24時間クールダウンを適用する。
  void _dismissImplicitly() {
    if (_isDialogShowing) {
      _isDialogShowing = false;
      ref.read(backgroundLocationMonitorProvider.notifier).dismissPrompt();
      // ダイアログが表示中の場合はポップする
      if (mounted && Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
      }
    }
  }

  /// 「更新する」ボタン押下時の処理。
  /// GPS地区判定フローを開始し、失敗時はエラーダイアログを表示する。
  Future<void> _onAccept() async {
    _isDialogShowing = false;
    Navigator.of(context).pop(); // プロンプトダイアログを閉じる

    // acceptUpdate()を呼び出し（内部でdetectDistrict()を実行）
    try {
      await ref
          .read(backgroundLocationMonitorProvider.notifier)
          .acceptUpdate();

      // acceptUpdate完了後、GPS判定の状態を確認
      final gpsState = ref.read(gpsDetectionProvider);
      if (gpsState is GpsDetectionError) {
        // GPS判定失敗: エラーメッセージと手動遷移オプションを表示
        if (mounted) {
          _showDetectionErrorDialog(gpsState.message);
        }
      }
    } catch (_) {
      // acceptUpdate自体が例外を投げた場合
      if (mounted) {
        _showDetectionErrorDialog(
          'GPS地区判定に失敗しました。手動で地域を選択してください。',
        );
      }
    }
  }

  /// 「後で」ボタン押下時の処理。
  /// 24時間のクールダウンを設定する。
  void _onDismiss() {
    _isDialogShowing = false;
    Navigator.of(context).pop(); // プロンプトダイアログを閉じる
    ref.read(backgroundLocationMonitorProvider.notifier).dismissPrompt();
  }

  /// GPS判定失敗時のエラーダイアログを表示する。
  /// 手動で地域選択画面に遷移できるオプションを提示する。
  void _showDetectionErrorDialog(String errorMessage) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('地域設定の更新に失敗'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(errorMessage),
              const SizedBox(height: 12),
              const Text('手動で地域選択画面から設定を変更できます。'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
              },
              child: const Text('閉じる'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                // 地域選択画面に遷移
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const RegionSelectionScreen(),
                  ),
                );
              },
              child: const Text('地域選択画面へ'),
            ),
          ],
        );
      },
    );
  }

  /// 位置変化検出のプロンプトダイアログを表示する。
  void _showPromptDialog(double distanceKm) {
    if (_isDialogShowing) return;
    _isDialogShowing = true;

    showDialog(
      context: context,
      barrierDismissible: false, // 外側タップで閉じない（明示的な選択を要求）
      builder: (dialogContext) {
        return PopScope(
          // 戻るボタンで閉じた場合は暗黙的dismiss
          canPop: true,
          onPopInvokedWithResult: (didPop, _) {
            if (didPop && _isDialogShowing) {
              _isDialogShowing = false;
              ref
                  .read(backgroundLocationMonitorProvider.notifier)
                  .dismissPrompt();
            }
          },
          child: AlertDialog(
            title: const Text('地域設定の更新'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '現在地が設定地区から離れています。地域設定を更新しますか？',
                ),
                const SizedBox(height: 12),
                Text(
                  '約${distanceKm.toStringAsFixed(1)}km離れています',
                  style: TextStyle(
                    color: Colors.grey[600],
                    fontSize: 13,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: _onDismiss,
                child: const Text('後で'),
              ),
              ElevatedButton(
                onPressed: _onAccept,
                child: const Text('更新する'),
              ),
            ],
          ),
        );
      },
    ).then((_) {
      // ダイアログが何らかの理由で閉じられた場合のフォールバック
      // （_isDialogShowingがまだtrueなら暗黙的dismissとして扱う）
      if (_isDialogShowing) {
        _isDialogShowing = false;
        ref.read(backgroundLocationMonitorProvider.notifier).dismissPrompt();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // BackgroundMonitorPrompting状態をリッスンし、ダイアログを表示
    ref.listen<BackgroundMonitorState>(
      backgroundLocationMonitorProvider,
      (previous, next) {
        if (next is BackgroundMonitorPrompting && !_isDialogShowing) {
          // 次フレームでダイアログを表示（buildの最中にshowDialogを呼ばないため）
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              _showPromptDialog(next.distanceKm);
            }
          });
        }
      },
    );

    return widget.child;
  }
}
