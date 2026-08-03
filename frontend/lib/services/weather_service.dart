import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/weather.dart';

/// Open-Meteo APIを使用した天気予報サービス
///
/// APIキー不要で最大16日分の日次天気予報を取得する。
/// 愛媛県の各市町村の代表座標をもとに予報を取得する。
class WeatherService {
  /// 愛媛県のデフォルト座標（松山市）
  static const double _defaultLatitude = 33.8416;
  static const double _defaultLongitude = 132.7657;

  /// 市区町村IDに対応する座標マップ
  static const Map<String, List<double>> _coordinates = {
    '38201': [33.8416, 132.7657], // 松山市
    '38202': [34.0661, 132.9977], // 今治市
    '38203': [33.2217, 132.5606], // 宇和島市
    '38204': [33.4633, 132.4231], // 八幡浜市
    '38205': [33.9601, 133.2831], // 新居浜市
    '38206': [33.9200, 133.1831], // 西条市
    '38207': [33.5047, 132.5461], // 大洲市
    '38210': [33.7567, 132.7017], // 伊予市
    '38213': [33.9803, 133.5497], // 四国中央市
    '38214': [33.3722, 132.5128], // 西予市
    '38215': [33.7906, 132.8706], // 東温市
    '38356': [34.2500, 133.2000], // 上島町
    '38386': [33.6500, 132.9000], // 久万高原町
    '38401': [33.7900, 132.7100], // 松前町
    '38402': [33.7400, 132.7900], // 砥部町
    '38422': [33.5300, 132.6400], // 内子町
    '38442': [33.4900, 132.3500], // 伊方町
    '38484': [33.2200, 132.7200], // 松野町
    '38488': [33.2500, 132.7700], // 鬼北町
    '38506': [32.9600, 132.5800], // 愛南町
  };

  /// 地区IDから市区町村IDを抽出する
  String _getMunicipalityId(String districtId) {
    // districtIdは "38201-01" 形式 → "-" より前が市区町村ID
    return districtId.split('-').first;
  }

  /// 指定地区の天気予報を取得する（最大16日分）
  ///
  /// [districtId] 地区ID（例: "38201-01"）
  /// 返り値: 日付→DailyWeatherのMap
  Future<Map<DateTime, DailyWeather>> getForecast(String districtId) async {
    final municipalityId = _getMunicipalityId(districtId);
    final coords = _coordinates[municipalityId] ??
        [_defaultLatitude, _defaultLongitude];
    final latitude = coords[0];
    final longitude = coords[1];

    final url = Uri.parse(
      'https://api.open-meteo.com/v1/forecast'
      '?latitude=$latitude'
      '&longitude=$longitude'
      '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'
      '&timezone=Asia%2FTokyo'
      '&forecast_days=16',
    );

    try {
      final response = await http.get(url);

      if (response.statusCode != 200) {
        return {};
      }

      final data = json.decode(response.body) as Map<String, dynamic>;
      final daily = data['daily'] as Map<String, dynamic>;

      final times = (daily['time'] as List<dynamic>).cast<String>();
      final weatherCodes =
          (daily['weather_code'] as List<dynamic>).cast<int>();
      final tempMaxList =
          (daily['temperature_2m_max'] as List<dynamic>).cast<num>();
      final tempMinList =
          (daily['temperature_2m_min'] as List<dynamic>).cast<num>();
      final precipProbList =
          (daily['precipitation_probability_max'] as List<dynamic>?)
              ?.cast<num>() ??
          List.filled(times.length, 0);

      final Map<DateTime, DailyWeather> forecast = {};

      for (int i = 0; i < times.length; i++) {
        final date = DateTime.parse(times[i]);
        final dateKey = DateTime(date.year, date.month, date.day);

        forecast[dateKey] = DailyWeather(
          date: dateKey,
          condition: weatherConditionFromCode(weatherCodes[i]),
          temperatureMax: tempMaxList[i].toDouble(),
          temperatureMin: tempMinList[i].toDouble(),
          precipitationProbability: precipProbList[i].toDouble(),
        );
      }

      return forecast;
    } catch (_) {
      // ネットワークエラー時は空を返す
      return {};
    }
  }
}
