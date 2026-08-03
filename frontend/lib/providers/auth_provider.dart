import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/auth_service.dart';

/// AuthServiceのプロバイダー
final authServiceProvider = Provider<AuthService>((ref) => AuthService());

/// 認証状態を管理するプロバイダー
///
/// ログイン済みの場合はユーザー名を保持し、
/// 未ログイン時はnullを返す。
final authStateProvider =
    StateNotifierProvider<AuthStateNotifier, AsyncValue<AuthState>>((ref) {
  final service = ref.watch(authServiceProvider);
  return AuthStateNotifier(service);
});

/// 認証状態
class AuthState {
  final bool isLoggedIn;
  final String? username;
  final bool hasSkippedLogin;

  const AuthState({
    required this.isLoggedIn,
    this.username,
    this.hasSkippedLogin = false,
  });

  static const loggedOut = AuthState(isLoggedIn: false);
  static const skipped = AuthState(isLoggedIn: false, hasSkippedLogin: true);
}

/// 認証状態のStateNotifier
class AuthStateNotifier extends StateNotifier<AsyncValue<AuthState>> {
  final AuthService _service;

  AuthStateNotifier(this._service) : super(const AsyncValue.loading()) {
    _checkLoginState();
  }

  /// 保存済みトークンからログイン状態を復元する
  Future<void> _checkLoginState() async {
    try {
      final isLoggedIn = await _service.isLoggedIn();
      if (isLoggedIn) {
        final username = await _service.getUsername();
        state = AsyncValue.data(AuthState(isLoggedIn: true, username: username));
      } else {
        final hasSkipped = await _service.hasSkippedLogin();
        if (hasSkipped) {
          state = const AsyncValue.data(AuthState.skipped);
        } else {
          state = const AsyncValue.data(AuthState.loggedOut);
        }
      }
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// ユーザー登録
  Future<void> register(
    String username,
    String password, {
    int? age,
    String? gender,
    String? districtId,
  }) async {
    try {
      await _service.register(username, password,
          age: age, gender: gender, districtId: districtId);
      state = AsyncValue.data(AuthState(isLoggedIn: true, username: username));
    } catch (e, st) {
      // エラーをre-throwして呼び出し元でハンドリング
      rethrow;
    }
  }

  /// ログイン
  Future<void> login(String username, String password) async {
    try {
      await _service.login(username, password);
      state = AsyncValue.data(AuthState(isLoggedIn: true, username: username));
    } catch (e, st) {
      rethrow;
    }
  }

  /// ログインをスキップして利用する
  Future<void> skipLogin() async {
    await _service.setSkippedLogin();
    state = const AsyncValue.data(AuthState.skipped);
  }

  /// ログアウト
  Future<void> logout() async {
    await _service.logout();
    state = const AsyncValue.data(AuthState.loggedOut);
  }
}
