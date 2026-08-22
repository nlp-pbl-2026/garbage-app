import 'dart:convert';

import 'package:flutter/services.dart';

/// 自治体名ローマ字変換サービス
///
/// `assets/data/municipality_romanization.json` から日本語→ローマ字の
/// マッピングデータを読み込み、自治体名のローマ字読みを提供する。
///
/// シングルトンパターンで実装し、一度ロードしたデータをキャッシュする。
class RomanizationService {
  RomanizationService._();

  static final RomanizationService _instance = RomanizationService._();

  /// シングルトンインスタンスを取得する
  static RomanizationService get instance => _instance;

  /// 日本語名 → ローマ字名のマッピング
  Map<String, String>? _romanizationMap;

  /// データがロード済みかどうか
  bool get isLoaded => _romanizationMap != null;

  /// JSONアセットからローマ字マッピングデータを読み込む
  ///
  /// 既にロード済みの場合は何もしない。
  /// テスト用に [assetBundle] を差し替え可能にしている。
  Future<void> load({AssetBundle? assetBundle}) async {
    if (_romanizationMap != null) return;

    final bundle = assetBundle ?? rootBundle;
    final jsonString = await bundle.loadString(
      'assets/data/municipality_romanization.json',
    );
    final Map<String, dynamic> decoded =
        json.decode(jsonString) as Map<String, dynamic>;
    _romanizationMap =
        decoded.map((key, value) => MapEntry(key, value as String));
  }

  /// 指定した日本語自治体名のローマ字読みを返す
  ///
  /// マッピングに存在しない場合は `null` を返す。
  /// [load] が呼ばれていない場合も `null` を返す。
  String? getRomanizedName(String japaneseName) {
    return _romanizationMap?[japaneseName];
  }

  /// 自治体名の表示用文字列を生成する
  ///
  /// - [isJapaneseLocale] が `true` の場合: 日本語名のみ返す（例: "松山市"）
  /// - [isJapaneseLocale] が `false` の場合: ローマ字読み付きで返す（例: "松山市 (Matsuyama-shi)"）
  /// - ローマ字マッピングが見つからない場合: 日本語名のみ返す
  String formatMunicipalityName(String japaneseName,
      {required bool isJapaneseLocale}) {
    if (isJapaneseLocale) {
      return japaneseName;
    }

    final romanized = getRomanizedName(japaneseName);
    if (romanized == null) {
      return japaneseName;
    }

    return '$japaneseName ($romanized)';
  }

  /// テスト用: キャッシュをクリアする
  void reset() {
    _romanizationMap = null;
  }
}
