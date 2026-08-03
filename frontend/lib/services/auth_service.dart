import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// 認証サービス
///
/// バックエンドAPIと通信してユーザー登録・ログイン・トークン管理を行う。
class AuthService {
  /// バックエンドのベースURL（開発時）
  /// TODO: 本番環境では環境変数等で切り替え
  static const String _baseUrl = 'http://localhost:8000';

  static const String _tokenKey = 'auth_token';
  static const String _usernameKey = 'auth_username';
  static const String _skippedKey = 'auth_skipped';

  /// ユーザー登録
  ///
  /// 成功時はトークンを返し、ローカルに保存する。
  /// エラー時はエラーメッセージを含むExceptionをthrowする。
  Future<String> register(
    String username,
    String password, {
    int? age,
    String? gender,
    String? districtId,
  }) async {
    final body = <String, dynamic>{
      'username': username,
      'password': password,
    };
    if (age != null) body['age'] = age;
    if (gender != null) body['gender'] = gender;
    if (districtId != null) body['district_id'] = districtId;

    final response = await http.post(
      Uri.parse('$_baseUrl/api/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(body),
    );

    if (response.statusCode == 201) {
      final data = json.decode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      await _saveToken(token, username);
      return token;
    } else if (response.statusCode == 409) {
      throw Exception('このユーザー名は既に使用されています');
    } else {
      throw Exception('登録に失敗しました');
    }
  }

  /// ログイン
  ///
  /// 成功時はトークンを返し、ローカルに保存する。
  Future<String> login(String username, String password) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'username': username,
        'password': password,
      }),
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      await _saveToken(token, username);
      return token;
    } else if (response.statusCode == 401) {
      throw Exception('ユーザー名またはパスワードが正しくありません');
    } else {
      throw Exception('ログインに失敗しました');
    }
  }

  /// ログアウト（ローカルのトークンを削除）
  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_usernameKey);
  }

  /// 保存済みトークンを取得する
  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  /// 保存済みユーザー名を取得する
  Future<String?> getUsername() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_usernameKey);
  }

  /// ログイン状態かどうか
  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null;
  }

  /// ログインスキップ済みかどうか
  Future<bool> hasSkippedLogin() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_skippedKey) ?? false;
  }

  /// ログインスキップフラグを保存する
  Future<void> setSkippedLogin() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_skippedKey, true);
  }

  /// ユーザー設定をサーバーに保存する
  Future<void> saveSettings(Map<String, dynamic> settings) async {
    final token = await getToken();
    if (token == null) return;

    await http.put(
      Uri.parse('$_baseUrl/api/auth/settings'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: json.encode({'settings': settings}),
    );
  }

  /// サーバーからユーザー設定を取得する
  Future<Map<String, dynamic>?> loadSettings() async {
    final token = await getToken();
    if (token == null) return null;

    final response = await http.get(
      Uri.parse('$_baseUrl/api/auth/me'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as Map<String, dynamic>;
      return data['settings'] as Map<String, dynamic>?;
    }
    return null;
  }

  /// トークンとユーザー名をローカルに保存する
  Future<void> _saveToken(String token, String username) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    await prefs.setString(_usernameKey, username);
  }
}
