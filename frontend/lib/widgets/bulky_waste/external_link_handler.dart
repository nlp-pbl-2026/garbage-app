import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../models/bulky_waste.dart';

/// 外部申し込み窓口への遷移を処理するウィジェット
///
/// [MunicipalityConfig] の `applicationMethod` に応じて、
/// Webフォームボタン・電話ボタン・両方を表示する。
///
/// - Webボタンタップ: url_launcher でデフォルトブラウザ起動
/// - 電話ボタンタップ: 確認ダイアログ → tel: スキームで発信
/// - 起動失敗時: エラーメッセージ + コピー可能テキスト表示
///
/// 要件6.1〜6.7: 外部申し込み窓口への遷移
class ExternalLinkHandler extends StatelessWidget {
  /// 自治体の申し込み方法
  final ApplicationMethod applicationMethod;

  /// WebフォームURL（web_form または both の場合に必須）
  final String? webFormUrl;

  /// 電話番号（phone または both の場合に必須）
  final String? phoneNumber;

  const ExternalLinkHandler({
    super.key,
    required this.applicationMethod,
    this.webFormUrl,
    this.phoneNumber,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_showWebButton) ...[
          _buildWebFormButton(context),
          if (_showPhoneButton) const SizedBox(height: 12),
        ],
        if (_showPhoneButton) _buildPhoneButton(context),
      ],
    );
  }

  /// Webフォームボタンを表示するかどうか
  bool get _showWebButton =>
      applicationMethod == ApplicationMethod.webForm ||
      applicationMethod == ApplicationMethod.both;

  /// 電話ボタンを表示するかどうか
  bool get _showPhoneButton =>
      applicationMethod == ApplicationMethod.phone ||
      applicationMethod == ApplicationMethod.both;

  /// Webフォームボタン
  Widget _buildWebFormButton(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: () => _launchWebForm(context),
      icon: const Icon(Icons.open_in_browser),
      label: const Text('Webで申し込む'),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 14),
      ),
    );
  }

  /// 電話ボタン
  Widget _buildPhoneButton(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: () => _showPhoneConfirmDialog(context),
      icon: const Icon(Icons.phone),
      label: const Text('電話で申し込む'),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 14),
      ),
    );
  }

  /// Webフォームを外部ブラウザで起動
  Future<void> _launchWebForm(BuildContext context) async {
    final url = webFormUrl;
    if (url == null || url.isEmpty) return;

    try {
      final uri = Uri.parse(url);
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.platformDefault,
      );
      if (!launched) {
        if (context.mounted) {
          _showUrlError(context, url);
        }
      }
    } catch (e) {
      if (context.mounted) {
        _showUrlError(context, url);
      }
    }
  }

  /// 電話発信確認ダイアログを表示
  Future<void> _showPhoneConfirmDialog(BuildContext context) async {
    final number = phoneNumber;
    if (number == null || number.isEmpty) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('電話発信の確認'),
        content: Text('$number に電話しますか？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('キャンセル'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('発信'),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      await _launchPhone(context, number);
    }
  }

  /// 電話を発信
  Future<void> _launchPhone(BuildContext context, String number) async {
    try {
      final uri = Uri(scheme: 'tel', path: number);
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );
      if (!launched) {
        if (context.mounted) {
          _showPhoneError(context, number);
        }
      }
    } catch (e) {
      if (context.mounted) {
        _showPhoneError(context, number);
      }
    }
  }

  /// URL起動失敗時のエラー表示
  void _showUrlError(BuildContext context, String url) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('URLを開けませんでした。以下のURLをコピーしてブラウザで開いてください。'),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: SelectableText(
                    url,
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.copy, color: Colors.white, size: 18),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: url));
                    ScaffoldMessenger.of(context).hideCurrentSnackBar();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('URLをコピーしました'),
                        duration: Duration(seconds: 2),
                      ),
                    );
                  },
                  tooltip: 'URLをコピー',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
          ],
        ),
        duration: const Duration(seconds: 10),
      ),
    );
  }

  /// 電話起動失敗時のエラー表示
  void _showPhoneError(BuildContext context, String number) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('電話を発信できませんでした。以下の番号に直接おかけください。'),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: SelectableText(
                    number,
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.copy, color: Colors.white, size: 18),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: number));
                    ScaffoldMessenger.of(context).hideCurrentSnackBar();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('電話番号をコピーしました'),
                        duration: Duration(seconds: 2),
                      ),
                    );
                  },
                  tooltip: '電話番号をコピー',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
          ],
        ),
        duration: const Duration(seconds: 10),
      ),
    );
  }
}
