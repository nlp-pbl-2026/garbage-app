import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/municipality_data_service.dart';

final municipalityDataProvider =
    Provider<MunicipalityDataService>((ref) => MunicipalityDataService());
