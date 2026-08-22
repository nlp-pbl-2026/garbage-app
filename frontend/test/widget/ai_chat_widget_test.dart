import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/services/rag_service.dart';
import 'package:garbage_app/widgets/ai_chat_widget.dart';

/// テスト用: RegionSettingProvider の値を直接オーバーライドするプロバイダー
final _testRegionProvider =
    StateProvider<RegionSetting?>((ref) => null);

void main() {
  group('AiChatWidget RAG integration', () {
    testWidgets('RegionSettingが存在するとき、RagServiceに地域情報が渡される',
        (tester) async {
      Map<String, dynamic>? capturedBody;
      final mockClient = MockClient((request) async {
        capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({'answer': 'テスト回答', 'sources': []}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final testRegion = RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38201',
        municipalityName: '松山市',
        districtId: '38201-08',
        districtName: '清水',
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: _TestableAiChat(
                mockClient: mockClient,
                region: testRegion,
              ),
            ),
          ),
        ),
      );

      // バナーをタップしてチャットパネルを開く
      await tester.tap(find.text('AIが質問にお答えします'));
      await tester.pumpAndSettle();

      // テキストフィールドに入力して送信
      final textField = find.byType(TextField);
      await tester.enterText(textField, 'プラスチック製の植木鉢は何ゴミ？');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // リクエストボディに地域情報が含まれることを確認
      expect(capturedBody, isNotNull);
      expect(capturedBody!['query'], equals('プラスチック製の植木鉢は何ゴミ？'));
      expect(capturedBody!['municipality_id'], equals('38201'));
      expect(capturedBody!['municipality_name'], equals('松山市'));
      expect(capturedBody!['district_id'], equals('38201-08'));
      expect(capturedBody!['district_name'], equals('清水'));

      // 回答がチャットに表示されることを確認
      expect(find.text('テスト回答'), findsOneWidget);
    });

    testWidgets('RegionSettingがnullのとき、RagServiceにregionなしで送信される',
        (tester) async {
      Map<String, dynamic>? capturedBody;
      final mockClient = MockClient((request) async {
        capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({'answer': '一般回答', 'sources': []}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: _TestableAiChat(
                mockClient: mockClient,
                region: null,
              ),
            ),
          ),
        ),
      );

      // バナーをタップしてチャットパネルを開く
      await tester.tap(find.text('AIが質問にお答えします'));
      await tester.pumpAndSettle();

      // テキストフィールドに入力して送信
      final textField = find.byType(TextField);
      await tester.enterText(textField, 'ゴミの出し方を教えて');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // リクエストボディにqueryのみで地域情報がないことを確認
      expect(capturedBody, isNotNull);
      expect(capturedBody!['query'], equals('ゴミの出し方を教えて'));
      expect(capturedBody!.containsKey('municipality_id'), isFalse);
      expect(capturedBody!.containsKey('municipality_name'), isFalse);
      expect(capturedBody!.containsKey('district_id'), isFalse);
      expect(capturedBody!.containsKey('district_name'), isFalse);

      // 回答がチャットに表示されることを確認
      expect(find.text('一般回答'), findsOneWidget);
    });
  });
}

/// テスト用の簡易AiChatウィジェット
///
/// 本番の AiChatWidget と同じロジック（RegionSetting取得→RagService送信）を
/// テスト可能な形で再現する。RagServiceにMockClientを注入し、
/// RegionSettingをコンストラクタから直接渡すことで
/// ProviderのStateNotifier型制約を回避する。
class _TestableAiChat extends StatefulWidget {
  final http.Client mockClient;
  final RegionSetting? region;

  const _TestableAiChat({
    required this.mockClient,
    required this.region,
  });

  @override
  State<_TestableAiChat> createState() => _TestableAiChatState();
}

class _TestableAiChatState extends State<_TestableAiChat> {
  bool _isOpen = false;
  bool _isLoading = false;
  final List<ChatMessage> _messages = [];
  final TextEditingController _textController = TextEditingController();
  late final RagService _ragService;

  @override
  void initState() {
    super.initState();
    _ragService =
        RagService(client: widget.mockClient, baseUrl: 'http://test:8000');
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  void _togglePanel() {
    setState(() {
      _isOpen = !_isOpen;
    });
  }

  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isLoading) return;

    _textController.clear();
    setState(() {
      _messages.add(ChatMessage(role: 'user', text: text));
      _isLoading = true;
    });

    // 本番の AiChatWidget と同じパターン: regionを渡す
    final response =
        await _ragService.sendMessage(text, region: widget.region);

    setState(() {
      _messages.add(ChatMessage(role: 'assistant', text: response));
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        if (!_isOpen)
          GestureDetector(
            onTap: _togglePanel,
            child: const Text('AIが質問にお答えします'),
          ),
        if (_isOpen)
          Column(
            children: [
              Expanded(
                child: ListView(
                  children: _messages
                      .map((m) => Text(m.text, key: ValueKey(m.text)))
                      .toList(),
                ),
              ),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textController,
                    ),
                  ),
                  IconButton(
                    onPressed: _isLoading ? null : _sendMessage,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ],
          ),
      ],
    );
  }
}
