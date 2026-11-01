import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/collection_status.dart';

class CollectionStatusNotice extends StatelessWidget {
  final CollectionStatus status;
  final bool showMessage;
  const CollectionStatusNotice({super.key, required this.status, this.showMessage = true});

  @override
  Widget build(BuildContext context) {
    if (!status.isUnverified) return const SizedBox.shrink();
    final uri = Uri.tryParse(status.sourceUrl ?? '');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('収集日未確認', style: TextStyle(fontWeight: FontWeight.bold)),
          if (showMessage) Text(status.message ?? 'この区分の収集日は未確認です。'),
          if (uri != null && ['https', 'http'].contains(uri.scheme))
            TextButton.icon(
              icon: const Icon(Icons.open_in_new, size: 16),
              label: const Text('公式カレンダーを確認'),
              onPressed: () async {
                try {
                  if (await launchUrl(uri, mode: LaunchMode.externalApplication)) return;
                } catch (_) {
                  // The source URL remains visible when external launch is unavailable.
                }
                if (context.mounted) {
                  ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text('公式資料を開けませんでした。${status.sourceUrl}')));
                }
              },
            ),
        ]),
      ),
    );
  }
}
