/// 天気予報のデータモデル

import 'package:flutter/material.dart';

/// 日次天気予報データ
class DailyWeather {
  final DateTime date;
  final WeatherCondition condition;
  final double temperatureMax;
  final double temperatureMin;
  final double precipitationProbability;

  DailyWeather({
    required this.date,
    required this.condition,
    required this.temperatureMax,
    required this.temperatureMin,
    required this.precipitationProbability,
  });
}

/// 天気コード → 天気状態のマッピング
enum WeatherCondition {
  sunny,
  partlyCloudy,
  cloudy,
  rainy,
  heavyRain,
  snowy,
  thunderstorm,
  foggy,
}

/// WMOの天気コードからWeatherConditionへ変換
WeatherCondition weatherConditionFromCode(int code) {
  // WMO Weather interpretation codes
  // https://open-meteo.com/en/docs
  if (code == 0) return WeatherCondition.sunny;
  if (code <= 3) return WeatherCondition.partlyCloudy;
  if (code <= 49) return WeatherCondition.foggy;
  if (code <= 59) return WeatherCondition.rainy; // drizzle
  if (code <= 65) return WeatherCondition.rainy;
  if (code <= 67) return WeatherCondition.heavyRain; // freezing rain
  if (code <= 77) return WeatherCondition.snowy;
  if (code <= 82) return WeatherCondition.heavyRain; // rain showers
  if (code <= 86) return WeatherCondition.snowy; // snow showers
  if (code <= 99) return WeatherCondition.thunderstorm;
  return WeatherCondition.cloudy;
}

/// 天気状態に対応するアイコンを取得
IconData weatherIcon(WeatherCondition condition) {
  switch (condition) {
    case WeatherCondition.sunny:
      return Icons.wb_sunny;
    case WeatherCondition.partlyCloudy:
      return Icons.cloud_queue;
    case WeatherCondition.cloudy:
      return Icons.cloud;
    case WeatherCondition.rainy:
      return Icons.umbrella;
    case WeatherCondition.heavyRain:
      return Icons.thunderstorm;
    case WeatherCondition.snowy:
      return Icons.ac_unit;
    case WeatherCondition.thunderstorm:
      return Icons.flash_on;
    case WeatherCondition.foggy:
      return Icons.foggy;
  }
}

/// 天気状態に対応する色を取得
Color weatherColor(WeatherCondition condition) {
  switch (condition) {
    case WeatherCondition.sunny:
      return const Color(0xFFFF9800);
    case WeatherCondition.partlyCloudy:
      return const Color(0xFF78909C);
    case WeatherCondition.cloudy:
      return const Color(0xFF607D8B);
    case WeatherCondition.rainy:
      return const Color(0xFF2196F3);
    case WeatherCondition.heavyRain:
      return const Color(0xFF1565C0);
    case WeatherCondition.snowy:
      return const Color(0xFF81D4FA);
    case WeatherCondition.thunderstorm:
      return const Color(0xFF6A1B9A);
    case WeatherCondition.foggy:
      return const Color(0xFF90A4AE);
  }
}

/// 天気状態の日本語ラベル
String weatherLabel(WeatherCondition condition) {
  switch (condition) {
    case WeatherCondition.sunny:
      return '晴れ';
    case WeatherCondition.partlyCloudy:
      return '曇り時々晴れ';
    case WeatherCondition.cloudy:
      return '曇り';
    case WeatherCondition.rainy:
      return '雨';
    case WeatherCondition.heavyRain:
      return '大雨';
    case WeatherCondition.snowy:
      return '雪';
    case WeatherCondition.thunderstorm:
      return '雷雨';
    case WeatherCondition.foggy:
      return '霧';
  }
}
