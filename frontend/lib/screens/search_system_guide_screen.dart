import 'package:flutter/material.dart';

import '../services/waste_guide_service.dart';
import '../widgets/search_pipeline_view.dart';

class SearchSystemGuideScreen extends StatelessWidget {
  const SearchSystemGuideScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F4EE),
      appBar: AppBar(title: const Text('あいまい検索の仕組み')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 780),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Text(
                'ひとことを、地域に合った答えへ。',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 10),
              const Text(
                '一般的なAI知識だけで答えず、松山市・清水地区の資料を探してから分別と収集日を案内します。',
                style: TextStyle(
                    fontSize: 15, height: 1.7, color: Color(0xFF52645C)),
              ),
              const SizedBox(height: 24),
              const SearchPipelineView(
                stage: SearchPipelineStage.completed,
                compact: true,
              ),
              const SizedBox(height: 24),
              _section(
                Icons.auto_fix_high_rounded,
                '1. 言い換える',
                'Amazon Nova Liteが「雨の日に使う長いやつ」のような表現を、資料で探しやすい言葉へ整えます。勝手に素材などを補いません。',
              ),
              _section(
                Icons.travel_explore_rounded,
                '2. 地域資料を探す',
                'Amazon Bedrock Knowledge Baseが、松山市・清水地区のごみ分別資料から関連度の高い根拠を取得します。これがRAGです。',
              ),
              _section(
                Icons.psychology_alt_rounded,
                '3. 分別を判定する',
                'Nova Liteが取得した根拠だけを使って分類します。確信が足りない場合は断定せず、一つだけ追加質問を返します。',
              ),
              _section(
                Icons.event_available_rounded,
                '4. 収集日を照合する',
                '分類が確定した場合、清水地区のカレンダーと現在時刻を照合します。当日の収集終了後は次の収集日を案内します。',
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F3ED),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: const Text(
                  '品質改善のため、質問・回答・確信度・検索根拠のスコア・処理時間をAWS上に記録します。管理用の分析画面は分析キーで保護されています。',
                  style: TextStyle(height: 1.6, color: Color(0xFF294D3D)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static Widget _section(IconData icon, String title, String body) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: const BoxDecoration(
              color: Color(0xFF17352B),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: Colors.white, size: 21),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w800)),
                const SizedBox(height: 5),
                Text(body,
                    style: const TextStyle(
                        height: 1.65, color: Color(0xFF52645C))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
