import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/app_localizations.dart';
import '../providers/locale_provider.dart';
import '../services/gemini_service.dart';

/// チャットメッセージのモデル
class ChatMessage {
  final String role; // 'user' or 'assistant'
  final String text;

  const ChatMessage({required this.role, required this.text});
}

/// AI チャットウィジェット
///
/// 画面右端に縦書きバナーを表示し、タップでチャットパネルを展開する。
/// ゴミ分別に関する質問に特化したAIチャットボット。
/// ユーザーの選択言語でAI応答を生成する。
class AiChatWidget extends ConsumerStatefulWidget {
  const AiChatWidget({super.key});

  @override
  ConsumerState<AiChatWidget> createState() => _AiChatWidgetState();
}

class _AiChatWidgetState extends ConsumerState<AiChatWidget>
    with SingleTickerProviderStateMixin {
  bool _isOpen = false;
  bool _isLoading = false;
  final List<ChatMessage> _messages = [];
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final GeminiService _geminiService = GeminiService();

  static const double _panelWidth = 300.0;
  static const double _bannerWidth = 48.0;
  static const double _bannerHeight = 200.0;

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _togglePanel() {
    setState(() {
      _isOpen = !_isOpen;
    });
  }

  void _closePanel() {
    setState(() {
      _isOpen = false;
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
    _scrollToBottom();

    // 現在のロケールの言語コードを取得してsendMessageに渡す
    final languageCode = ref.read(localeProvider).languageCode;
    final response = await _geminiService.sendMessage(
      text,
      languageCode: languageCode,
    );

    setState(() {
      if (response != null) {
        _messages.add(ChatMessage(role: 'assistant', text: response));
      } else {
        // APIエラー時はARBファイルのローカライズ済みエラーメッセージを表示
        final errorMessage = AppLocalizations.of(context).aiErrorMessage;
        _messages.add(ChatMessage(role: 'assistant', text: errorMessage));
      }
      _isLoading = false;
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // チャットパネル（開いた状態）
        AnimatedPositioned(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          right: _isOpen ? 0 : -_panelWidth,
          top: 80,
          bottom: 0,
          width: _panelWidth,
          child: Material(
            elevation: 8,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(12),
            ),
            child: Container(
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(12),
                ),
              ),
              child: Column(
                children: [
                  _buildChatHeader(),
                  Expanded(child: _buildMessageList()),
                  _buildInputArea(),
                ],
              ),
            ),
          ),
        ),
        // バナー（閉じた状態 - 画面下半分に固定サイズで表示）
        AnimatedPositioned(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          right: _isOpen ? _panelWidth : 0,
          bottom: 120,
          width: _bannerWidth,
          height: _bannerHeight,
          child: _buildBanner(),
        ),
      ],
    );
  }

  /// 縦書きバナー
  Widget _buildBanner() {
    return GestureDetector(
      onTap: _togglePanel,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFFB3D4FC),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(8),
            bottomLeft: Radius.circular(8),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 4,
              offset: const Offset(-2, 0),
            ),
          ],
        ),
        child: Stack(
          children: [
            // 縦書きテキスト
            Center(
              child: RotatedBox(
                quarterTurns: 1,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Text(
                    'AIが質問にお答えします',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Colors.blueGrey[800],
                      letterSpacing: 2,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// チャットヘッダー
  Widget _buildChatHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFB3D4FC),
        border: Border(
          bottom: BorderSide(color: Colors.grey[300]!),
        ),
      ),
      child: Row(
        children: [
          const Icon(Icons.smart_toy, size: 20, color: Colors.blueGrey),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'AIアシスタント',
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: Colors.blueGrey,
              ),
            ),
          ),
          GestureDetector(
            onTap: _closePanel,
            child: const Icon(Icons.close, size: 22, color: Colors.blueGrey),
          ),
        ],
      ),
    );
  }

  /// メッセージリスト
  Widget _buildMessageList() {
    if (_messages.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'ゴミの分別やアプリの\n使い方を聞いてください！',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[500],
            ),
          ),
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: _messages.length + (_isLoading ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length && _isLoading) {
          return _buildLoadingBubble();
        }
        final message = _messages[index];
        return _buildMessageBubble(message);
      },
    );
  }

  /// メッセージ吹き出し
  Widget _buildMessageBubble(ChatMessage message) {
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        constraints: BoxConstraints(
          maxWidth: _panelWidth * 0.75,
        ),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFFDCF8C6) : Colors.grey[200],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          message.text,
          style: const TextStyle(fontSize: 13, height: 1.4),
        ),
      ),
    );
  }

  /// ローディング吹き出し
  Widget _buildLoadingBubble() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.grey[200],
          borderRadius: BorderRadius.circular(12),
        ),
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation<Color>(Colors.blueGrey),
          ),
        ),
      ),
    );
  }

  /// 入力エリア
  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          top: BorderSide(color: Colors.grey[300]!),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _textController,
              decoration: InputDecoration(
                hintText: '質問を入力...',
                hintStyle: TextStyle(fontSize: 13, color: Colors.grey[400]),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: BorderSide(color: Colors.grey[300]!),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: BorderSide(color: Colors.grey[300]!),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: const BorderSide(color: Color(0xFFB3D4FC)),
                ),
                isDense: true,
              ),
              style: const TextStyle(fontSize: 13),
              onSubmitted: (_) => _sendMessage(),
              textInputAction: TextInputAction.send,
            ),
          ),
          const SizedBox(width: 4),
          IconButton(
            onPressed: _isLoading ? null : _sendMessage,
            icon: Icon(
              Icons.send,
              color: _isLoading ? Colors.grey : Colors.blueGrey,
              size: 22,
            ),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 36,
              minHeight: 36,
            ),
          ),
        ],
      ),
    );
  }
}
