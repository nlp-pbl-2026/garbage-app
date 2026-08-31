import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/strings.dart';
import '../providers/auth_provider.dart';

/// 初回起動時のウェルカム画面。
///
/// AWSの公開デモは登録なしで使えるため「すぐ試す」を主導線にし、
/// ローカルBackend向けのログイン・登録フォームは必要なときだけ展開する。
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _showAccountForm = false;
  bool _registerMode = false;
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _errorMessage;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _continueWithoutLogin() async {
    setState(() => _isLoading = true);
    await ref.read(authStateProvider.notifier).skipLogin();
    if (!mounted) return;
    _finishIfPushed();
  }

  Future<void> _submitAccount() async {
    if (!_formKey.currentState!.validate()) return;
    if (_registerMode &&
        _passwordController.text != _confirmPasswordController.text) {
      setState(() => _errorMessage = '確認用パスワードが一致しません');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final notifier = ref.read(authStateProvider.notifier);
      if (_registerMode) {
        await notifier.register(
          _usernameController.text.trim(),
          _passwordController.text,
        );
      } else {
        await notifier.login(
          _usernameController.text.trim(),
          _passwordController.text,
        );
      }
      if (mounted) _finishIfPushed();
    } catch (error) {
      if (!mounted) return;
      final message = error.toString();
      setState(() {
        _errorMessage = message.contains('ClientException') ||
                message.contains('Failed to fetch') ||
                message.contains('SocketException') ||
                message.contains('Connection refused')
            ? 'アカウント機能に接続できません。登録なしでも検索できます。'
            : message.replaceAll('Exception: ', '');
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _finishIfPushed() {
    if (Navigator.of(context).canPop()) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final canPop = Navigator.of(context).canPop();

    return Scaffold(
      appBar: canPop
          ? AppBar(
              title: const Text('アカウント'),
              centerTitle: true,
            )
          : null,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!canPop) const SizedBox(height: 18),
                  _buildHero(colors),
                  const SizedBox(height: 24),
                  if (!canPop) ...[
                    FilledButton.icon(
                      key: const Key('continue-without-login'),
                      onPressed: _isLoading ? null : _continueWithoutLogin,
                      icon: _isLoading
                          ? const SizedBox.square(
                              dimension: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.arrow_forward_rounded),
                      label: const Text('ログインせず、すぐ試す'),
                      style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(56),
                        textStyle: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      '登録不要・AWSアカウント不要',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 12,
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 24),
                    OutlinedButton.icon(
                      key: const Key('account-form-toggle'),
                      onPressed: _isLoading
                          ? null
                          : () => setState(() {
                                _showAccountForm = !_showAccountForm;
                                _errorMessage = null;
                              }),
                      icon: Icon(
                        _showAccountForm
                            ? Icons.expand_less_rounded
                            : Icons.person_outline_rounded,
                      ),
                      label: Text(
                        _showAccountForm ? 'アカウント入力を閉じる' : 'アカウントを使う',
                      ),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                  ],
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 220),
                    transitionBuilder: (child, animation) => SizeTransition(
                      sizeFactor: animation,
                      alignment: Alignment.topCenter,
                      child: child,
                    ),
                    child: (_showAccountForm || canPop)
                        ? KeyedSubtree(
                            key: const Key('account-form'),
                            child: _buildAccountForm(colors),
                          )
                        : const SizedBox.shrink(
                            key: Key('account-form-collapsed'),
                          ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHero(ColorScheme colors) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [colors.primaryContainer, colors.tertiaryContainer],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        children: [
          Container(
            width: 68,
            height: 68,
            decoration: BoxDecoration(
              color: colors.surface.withValues(alpha: 0.92),
              borderRadius: BorderRadius.circular(22),
            ),
            child: Icon(
              Icons.recycling_rounded,
              size: 38,
              color: colors.primary,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            AppStrings.appName,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.2,
              color: colors.primary,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            '名前がわからなくても、\nちゃんと分別できる。',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 27,
              height: 1.28,
              fontWeight: FontWeight.w900,
              color: colors.onPrimaryContainer,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '見た目や使い方をひとこと入力。\n松山市の資料をもとにAIが探します。',
            textAlign: TextAlign.center,
            style: TextStyle(
              height: 1.55,
              color: colors.onPrimaryContainer.withValues(alpha: 0.78),
            ),
          ),
          const SizedBox(height: 20),
          const Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: [
              _FeatureChip(icon: Icons.search_rounded, label: 'あいまい検索'),
              _FeatureChip(icon: Icons.chat_bubble_outline, label: '追加質問'),
              _FeatureChip(icon: Icons.event_outlined, label: '収集日'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAccountForm(ColorScheme colors) {
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: colors.surfaceContainerLow,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: colors.outlineVariant),
        ),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('ログイン')),
                  ButtonSegment(value: true, label: Text('新規登録')),
                ],
                selected: {_registerMode},
                onSelectionChanged: (selection) => setState(() {
                  _registerMode = selection.first;
                  _errorMessage = null;
                }),
              ),
              const SizedBox(height: 18),
              TextFormField(
                controller: _usernameController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'ユーザー名',
                  prefixIcon: Icon(Icons.person_outline_rounded),
                ),
                validator: (value) {
                  if (value == null || value.trim().length < 3) {
                    return '3文字以上で入力してください';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _passwordController,
                obscureText: _obscurePassword,
                textInputAction:
                    _registerMode ? TextInputAction.next : TextInputAction.done,
                onFieldSubmitted: (_) {
                  if (!_registerMode) _submitAccount();
                },
                decoration: InputDecoration(
                  labelText: 'パスワード',
                  prefixIcon: const Icon(Icons.lock_outline_rounded),
                  suffixIcon: IconButton(
                    onPressed: () => setState(
                      () => _obscurePassword = !_obscurePassword,
                    ),
                    icon: Icon(
                      _obscurePassword
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                    ),
                  ),
                ),
                validator: (value) {
                  if (value == null || value.length < 6) {
                    return '6文字以上で入力してください';
                  }
                  return null;
                },
              ),
              if (_registerMode) ...[
                const SizedBox(height: 14),
                TextFormField(
                  controller: _confirmPasswordController,
                  obscureText: true,
                  onFieldSubmitted: (_) => _submitAccount(),
                  decoration: const InputDecoration(
                    labelText: 'パスワード（確認）',
                    prefixIcon: Icon(Icons.lock_reset_rounded),
                  ),
                  validator: (value) => value == null || value.isEmpty
                      ? '確認用パスワードを入力してください'
                      : null,
                ),
              ],
              if (_errorMessage != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: colors.errorContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _errorMessage!,
                    style: TextStyle(color: colors.onErrorContainer),
                  ),
                ),
              ],
              const SizedBox(height: 18),
              FilledButton(
                onPressed: _isLoading ? null : _submitAccount,
                child: Text(_registerMode ? '登録する' : 'ログイン'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _FeatureChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: colors.surface.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: colors.primary),
          const SizedBox(width: 5),
          Text(
            label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
