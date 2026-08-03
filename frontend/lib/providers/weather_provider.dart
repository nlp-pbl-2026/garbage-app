import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/weather.dart';
import '../services/weather_service.dart';
import 'region_provider.dart';

/// WeatherServiceのプロバイダー
final weatherServiceProvider =
    Provider<WeatherService>((ref) => WeatherService());

/// 天気予報データのFutureProvider
///
/// 設定された地域の天気予報（最大16日分）を取得する。
/// 地域未設定時は空のMapを返す。
final weatherForecastProvider =
    FutureProvider<Map<DateTime, DailyWeather>>((ref) async {
  final regionSettingAsync = ref.watch(regionSettingProvider);
  final regionSetting = regionSettingAsync.valueOrNull;

  if (regionSetting == null) {
    return {};
  }

  final service = ref.watch(weatherServiceProvider);
  return service.getForecast(regionSetting.districtId);
});
