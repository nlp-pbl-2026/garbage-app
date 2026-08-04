import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 利用規約同意状態のキー
const String _termsAcceptedKey = 'terms_accepted';

/// 利用規約同意状態のプロバイダー
///
/// SharedPreferencesから同意済みかどうかを読み込み、
/// 状態変更時に永続化する。
final termsAcceptedProvider =
    StateNotifierProvider<TermsAcceptedNotifier, AsyncValue<bool>>((ref) {
  return TermsAcceptedNotifier();
});

/// 利用規約同意状態を管理するStateNotifier
class TermsAcceptedNotifier extends StateNotifier<AsyncValue<bool>> {
  TermsAcceptedNotifier() : super(const AsyncValue.loading()) {
    _load();
  }

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final accepted = prefs.getBool(_termsAcceptedKey) ?? false;
      state = AsyncValue.data(accepted);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// 利用規約に同意する
  Future<void> accept() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_termsAcceptedKey, true);
      state = const AsyncValue.data(true);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}
