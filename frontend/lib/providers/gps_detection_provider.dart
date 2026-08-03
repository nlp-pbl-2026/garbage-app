import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/gps_detection.dart';
import '../services/abstract_district_matcher.dart';
import '../services/abstract_location_service.dart';
import '../services/abstract_reverse_geocoder.dart';
import '../services/district_matcher_service.dart';
import '../services/geocoding_cache.dart';
import '../services/geojson_resolver.dart';
import '../services/gps_location_service.dart';
import '../services/reverse_geocoding_service.dart';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/// GPS地区判定の状態を表すsealed class。
///
/// - [GpsDetectionIdle]: 初期状態（何も処理していない）
/// - [GpsDetectionLoading]: GPS判定処理中
/// - [GpsDetectionSuccess]: 判定成功（結果を保持）
/// - [GpsDetectionMultipleCandidates]: 複数候補（ユーザー選択待ち）
/// - [GpsDetectionError]: 判定失敗（エラーメッセージとエラー種別を保持）
sealed class GpsDetectionState {
  const GpsDetectionState();
}

/// 初期状態。GPS判定が未実行またはリセット後の状態。
class GpsDetectionIdle extends GpsDetectionState {
  const GpsDetectionIdle();
}

/// GPS判定処理中の状態。
class GpsDetectionLoading extends GpsDetectionState {
  const GpsDetectionLoading();
}

/// GPS判定成功の状態。判定された地区情報を保持する。
class GpsDetectionSuccess extends GpsDetectionState {
  final DistrictMatchResult result;

  const GpsDetectionSuccess(this.result);
}

/// GPS判定で複数候補が見つかった状態。ユーザーに選択を促す。
class GpsDetectionMultipleCandidates extends GpsDetectionState {
  final List<DistrictCandidate> candidates;
  final String? overflowMessage; // 50件超の場合のメッセージ

  const GpsDetectionMultipleCandidates({
    required this.candidates,
    this.overflowMessage,
  });
}

/// GPS判定失敗の状態。ユーザー向けエラーメッセージとエラー種別を保持する。
class GpsDetectionError extends GpsDetectionState {
  final String message;
  final GpsDetectionErrorType errorType;

  const GpsDetectionError(this.message, {this.errorType = GpsDetectionErrorType.unknown});
}

// ---------------------------------------------------------------------------
// Service Providers
// ---------------------------------------------------------------------------

/// AbstractLocationServiceのプロバイダー（テスト時にoverrideWithValue可能）
final gpsLocationServiceProvider =
    Provider<AbstractLocationService>((ref) => GpsLocationService());

/// AbstractReverseGeocoderのプロバイダー（テスト時にoverrideWithValue可能）
final reverseGeocodingServiceProvider =
    Provider<AbstractReverseGeocoder>((ref) => ReverseGeocodingService());

/// AbstractDistrictMatcherのプロバイダー（テスト時にoverrideWithValue可能）
final districtMatcherServiceProvider =
    Provider<AbstractDistrictMatcher>((ref) => DistrictMatcherService());

/// GeoJsonResolverのプロバイダー（テスト時にoverrideWithValue可能）
final geoJsonResolverProvider =
    Provider<GeoJsonResolver>((ref) => GeoJsonResolver());

/// GeocodingCacheのプロバイダー（テスト時にoverrideWithValue可能）
final geocodingCacheProvider =
    Provider<GeocodingCache>((ref) => GeocodingCache());

// ---------------------------------------------------------------------------
// Notifier
// ---------------------------------------------------------------------------

/// GPS地区判定の状態管理Notifier。
///
/// 権限確認→GPS座標取得→GeoJSON判定→逆ジオコーディング→地区マッチングの
/// 一連のフローを実行し、結果に応じて状態を更新する。
///
/// 判定フロー:
/// 1. GeoJsonResolverでオフライン判定を試行（isLoaded時のみ）
/// 2. 失敗時はGeocodingCacheを確認
/// 3. キャッシュミス時はReverseGeocoderでAPI呼び出し→結果をキャッシュ
/// 4. DistrictMatcherで地区マッチング（単一/複数候補）
class GpsDetectionNotifier extends StateNotifier<GpsDetectionState> {
  final AbstractLocationService _locationService;
  final AbstractReverseGeocoder _reverseGeocodingService;
  final AbstractDistrictMatcher _districtMatcherService;
  final GeoJsonResolver _geoJsonResolver;
  final GeocodingCache _geocodingCache;

  GpsDetectionNotifier(
    this._locationService,
    this._reverseGeocodingService,
    this._districtMatcherService,
    this._geoJsonResolver,
    this._geocodingCache,
  ) : super(const GpsDetectionIdle());

  /// GPS地区判定の一連のフローを実行する。
  ///
  /// 処理フロー:
  /// 1. 状態を Loading に遷移
  /// 2. GPS座標を取得（権限確認・リクエスト含む）
  /// 3. GeoJsonResolverでオフラインポリゴン判定を試行（isLoaded時のみ）
  ///    - 成功時: Success に遷移して早期リターン
  /// 4. GeoJSON失敗/null時: GeocodingCacheを確認
  ///    - キャッシュヒット: キャッシュされた住所を使用（APIスキップ）
  ///    - キャッシュミス: ReverseGeocoder呼び出し→結果をキャッシュ
  /// 5. DistrictMatcher.matchDistrict(address) を呼び出し
  ///    - 単一一致: Success に遷移
  /// 6. matchDistrictCandidates(address) を呼び出し
  ///    - 複数候補 (>1): MultipleCandidates に遷移
  ///    - 50件超: overflowMessage を含む
  /// 7. エラーハンドリング: GpsDetectionErrorType のマッピング
  Future<void> detectDistrict() async {
    state = const GpsDetectionLoading();

    try {
      // Step 1: GPS座標を取得（権限確認・リクエスト・精度バリデーション含む）
      final coordinate = await _locationService.getCurrentPosition();

      // Step 2: GeoJsonResolverでオフライン判定を試行（Req 6.2, 6.6）
      if (_geoJsonResolver.isLoaded) {
        final geoJsonResult = _geoJsonResolver.resolveDistrict(
          coordinate.latitude,
          coordinate.longitude,
        );
        if (geoJsonResult != null) {
          // GeoJSON判定成功: APIをスキップ (Req 6.3)
          state = GpsDetectionSuccess(geoJsonResult);
          return;
        }
      }
      // GeoJSON判定失敗またはisLoaded==false: 従来フローにフォールバック (Req 6.4, 6.6)

      // Step 3: GeocodingCache確認 → 逆ジオコーディング (Req 5.2)
      GeocodedAddress address;
      final cachedAddress = _geocodingCache.get(
        coordinate.latitude,
        coordinate.longitude,
      );

      if (cachedAddress != null) {
        // キャッシュヒット: API呼び出しをスキップ
        address = cachedAddress;
      } else {
        // キャッシュミス: ReverseGeocoder呼び出し
        address = await _reverseGeocodingService.getAddressFromCoordinates(
          coordinate.latitude,
          coordinate.longitude,
        );
        // 結果をキャッシュに保存
        _geocodingCache.put(
          coordinate.latitude,
          coordinate.longitude,
          address,
        );
      }

      // Step 4: choumei.csv データを読み込み（キャッシュ済みの場合はスキップ）
      await _districtMatcherService.loadChoumeiData();

      // Step 5: 地区マッチング（単一結果を試行）
      try {
        final result = _districtMatcherService.matchDistrict(address);
        state = GpsDetectionSuccess(result);
      } on DistrictNotFoundException {
        // Step 6: 単一一致が見つからない場合は候補リストを取得
        final candidates =
            _districtMatcherService.matchDistrictCandidates(address);

        if (candidates.length > 1) {
          // 複数候補がある場合
          String? overflowMessage;
          if (candidates.length >= 50) {
            // matchDistrictCandidatesは既に50件でキャップされているため、
            // 50件返されたら実際はそれ以上の候補が存在する可能性がある
            overflowMessage = '候補が多すぎます。住所を手動で選択してください。';
          }
          state = GpsDetectionMultipleCandidates(
            candidates: candidates,
            overflowMessage: overflowMessage,
          );
        } else if (candidates.length == 1) {
          // 候補が1件のみなら成功として扱う
          final candidate = candidates.first;
          state = GpsDetectionSuccess(
            DistrictMatchResult(
              districtNumber: candidate.districtNumber,
              districtName: candidate.districtName,
              matchedTown: candidate.townName,
            ),
          );
        } else {
          // 候補なし → DistrictNotFound エラー
          state = GpsDetectionError(
            DistrictNotFoundException().userMessage,
            errorType: GpsDetectionErrorType.districtNotFound,
          );
        }
      }
    } on GpsDetectionException catch (e) {
      state = GpsDetectionError(
        e.userMessage,
        errorType: _mapExceptionToErrorType(e),
      );
    } catch (_) {
      state = const GpsDetectionError(
        '予期しないエラーが発生しました。手動で地域を選択してください。',
        errorType: GpsDetectionErrorType.unknown,
      );
    }
  }

  /// 状態を初期状態（Idle）にリセットする。
  ///
  /// エラー後に再試行を可能にするため、または
  /// UIの表示をクリアするために使用する。
  void reset() {
    state = const GpsDetectionIdle();
  }

  /// 例外の型からエラー種別（GpsDetectionErrorType）へのマッピング。
  GpsDetectionErrorType _mapExceptionToErrorType(GpsDetectionException e) {
    return switch (e) {
      LocationPermissionDeniedException() => GpsDetectionErrorType.permissionDenied,
      LocationServiceDisabledException() => GpsDetectionErrorType.serviceDisabled,
      LocationTimeoutException() => GpsDetectionErrorType.timeout,
      LocationInaccurateException() => GpsDetectionErrorType.inaccurate,
      GeocodingFailedException() => GpsDetectionErrorType.geocodingFailed,
      OutOfAreaException() => GpsDetectionErrorType.outOfArea,
      DistrictNotFoundException() => GpsDetectionErrorType.districtNotFound,
    };
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

/// GPS地区判定のStateNotifierProvider。
///
/// UI層から `ref.watch(gpsDetectionProvider)` で状態を監視し、
/// `ref.read(gpsDetectionProvider.notifier).detectDistrict()` で判定を開始する。
final gpsDetectionProvider =
    StateNotifierProvider<GpsDetectionNotifier, GpsDetectionState>(
  (ref) => GpsDetectionNotifier(
    ref.watch(gpsLocationServiceProvider),
    ref.watch(reverseGeocodingServiceProvider),
    ref.watch(districtMatcherServiceProvider),
    ref.watch(geoJsonResolverProvider),
    ref.watch(geocodingCacheProvider),
  ),
);
