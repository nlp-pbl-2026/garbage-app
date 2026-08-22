// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Portuguese (`pt`).
class AppLocalizationsPt extends AppLocalizations {
  AppLocalizationsPt([String locale = 'pt']) : super(locale);

  @override
  String get appName => 'Ehime App de Lixo';

  @override
  String get categoryBurnable => 'Queimável';

  @override
  String get categoryRecyclable => 'Reciclável';

  @override
  String get categoryPlastic => 'Embalagens Plásticas';

  @override
  String get categoryPetBottle => 'Garrafas PET';

  @override
  String get categoryHazardous => 'Perigoso';

  @override
  String get tabSearch => 'Buscar';

  @override
  String get tabCalendar => 'Calendário';

  @override
  String get tabSettings => 'Configurações';

  @override
  String get tabImageInput => 'Imagem';

  @override
  String get regionSelectionTitle => 'Selecionar Região';

  @override
  String get selectPrefecture => 'Selecionar Província';

  @override
  String get selectMunicipality => 'Selecionar Município';

  @override
  String get selectDistrict => 'Selecionar Distrito';

  @override
  String get startWithRegion => 'Iniciar com esta região';

  @override
  String get searchTitle => 'Buscar Itens de Lixo';

  @override
  String get searchHint => 'Digite o nome do item (2+ caracteres)';

  @override
  String get popularItems => 'Itens Mais Buscados';

  @override
  String get multipleItemsFound => 'Vários itens semelhantes encontrados';

  @override
  String get multipleCategoriesNote => 'Ou varia conforme o item';

  @override
  String get itemDetailTitle => 'Detalhes do Item';

  @override
  String get nextCollectionDate => 'Próxima Data de Coleta';

  @override
  String get disposalMethod => 'Como Descartar';

  @override
  String get caution => 'Atenção';

  @override
  String get registerToCalendar => 'Adicionar ao Calendário';

  @override
  String get calendarTitle => 'Calendário de Coleta';

  @override
  String get nextCollection => 'Próxima Coleta';

  @override
  String get noSchedule => 'Nenhuma coleta programada para este dia';

  @override
  String get colorLegend => 'Legenda de Cores';

  @override
  String get settingsTitle => 'Configurações';

  @override
  String get regionSettings => 'Configurações de Região';

  @override
  String get changeRegion => 'Alterar Região';

  @override
  String get notificationSettings => 'Configurações de Notificação';

  @override
  String get languageSettings => 'Idioma';

  @override
  String get reminderToggle => 'Lembrete na véspera da coleta';

  @override
  String get reminderDescription =>
      'Notifica às 18:00 do dia anterior à coleta';

  @override
  String get noSearchResults => 'Nenhum item encontrado';

  @override
  String get dataLoadError => 'Falha ao carregar dados';

  @override
  String get regionDataError => 'Falha ao carregar dados da região';

  @override
  String get saveError => 'Falha ao salvar';

  @override
  String get regionNotSet => 'Região não configurada';

  @override
  String get dataOutdated =>
      'Os dados podem estar desatualizados. Conecte-se à internet para atualizar.';

  @override
  String get noOfflineData =>
      'Dados indisponíveis. É necessária uma conexão com a internet.';

  @override
  String get prefectureNotSelected => 'Selecione uma província';

  @override
  String get municipalityNotSelected => 'Selecione um município';

  @override
  String get districtNotSelected => 'Selecione um distrito';

  @override
  String get regionSaved => 'Configurações de região salvas';

  @override
  String get calendarRegistered => 'Adicionado ao calendário';

  @override
  String get calendarPermissionDenied =>
      'É necessária permissão de acesso ao calendário. Permita o acesso nas configurações do dispositivo.';

  @override
  String get retry => 'Tentar Novamente';

  @override
  String get back => 'Voltar';

  @override
  String get openSettings => 'Abrir Configurações';

  @override
  String get aiErrorMessage =>
      'Não foi possível concluir a solicitação. Tente novamente mais tarde.';

  @override
  String get aiBannerText => 'IA responde suas perguntas';

  @override
  String get aiAssistantTitle => 'Assistente IA';

  @override
  String get aiEmptyStateText => 'Pergunte sobre\na separação de lixo!';

  @override
  String get aiInputHint => 'Digite sua pergunta...';

  @override
  String get aiNoResponse => 'Sem resposta da IA.';

  @override
  String get aiValidationError => 'Por favor, insira uma pergunta.';

  @override
  String get aiTimeoutError =>
      'A solicitação expirou. Tente novamente mais tarde.';

  @override
  String get aiServiceUnavailable =>
      'Serviço de IA indisponível. Tente novamente mais tarde.';

  @override
  String get aiGenericError => 'Ocorreu um erro. Tente novamente mais tarde.';

  @override
  String get aiNetworkError =>
      'Erro de rede. Verifique sua conexão com a internet.';

  @override
  String get notificationTomorrowTitle => 'Lixo de Amanhã';

  @override
  String notificationTomorrowBody(String categories) {
    return 'Amanhã é dia de $categories';
  }

  @override
  String get notificationTodayTitle => 'Lixo de Hoje';

  @override
  String notificationTodayBody(String categories) {
    return 'Hoje é dia de $categories';
  }

  @override
  String municipalityRomanization(String japaneseName, String romanizedName) {
    return '$japaneseName ($romanizedName)';
  }

  @override
  String get bulkyWaste => 'Lixo Volumoso';

  @override
  String get regionRequired => 'Configuração de região necessária';

  @override
  String get searchTip => 'Pesquise itens que não sabe como descartar';

  @override
  String get searchTipDescription =>
      'Digite o nome do item para saber o método de descarte';

  @override
  String get searchByCategory => 'Pesquisar por Categoria';

  @override
  String get searchHistory => 'Histórico de Pesquisa';

  @override
  String get deleteAll => 'Excluir Tudo';

  @override
  String get searchResults => 'Resultados da Pesquisa';

  @override
  String get nextCollectionDates => 'Próximas Datas de Coleta';

  @override
  String get today => 'Hoje';

  @override
  String get tomorrow => 'Amanhã';

  @override
  String get dayAfterTomorrow => 'Depois de amanhã';

  @override
  String daysRemaining(int days) {
    return 'Faltam $days dias';
  }

  @override
  String collectionDaysFor(String category) {
    return 'Dias de Coleta de $category';
  }

  @override
  String get noUpcomingCollections =>
      'Nenhuma data de coleta futura encontrada';

  @override
  String get selectDate => 'Selecione uma data';

  @override
  String get exportCalendar => 'Exportar Calendário';

  @override
  String get categoryShortBurnable => 'Quei';

  @override
  String get categoryShortRecyclable => 'Reci';

  @override
  String get categoryShortPlastic => 'Plás';

  @override
  String get categoryShortPetBottle => 'PET';

  @override
  String get categoryShortHazardous => 'Peri';

  @override
  String get account => 'Conta';

  @override
  String get loggedIn => 'Conectado';

  @override
  String get changePassword => 'Alterar Senha';

  @override
  String get logout => 'Sair';

  @override
  String get loginOrRegister => 'Entrar / Registrar';

  @override
  String get loginSyncMessage =>
      'Faça login para sincronizar suas configurações';

  @override
  String get currentRegion => 'Região Atual';

  @override
  String get detectFromLocation => 'Redetectar pela localização atual';

  @override
  String get theme => 'Tema';

  @override
  String get themeSystem => 'Sistema';

  @override
  String get themeLight => 'Claro';

  @override
  String get themeDark => 'Escuro';

  @override
  String get other => 'Outros';

  @override
  String get faq => 'Perguntas Frequentes';

  @override
  String get termsOfService => 'Termos de Serviço';

  @override
  String get reminderNotificationDescription =>
      'Notifica no dia anterior e no dia da coleta';

  @override
  String get reminderSettingFailed => 'Falha ao configurar lembrete';

  @override
  String get regionSettingUpdated => 'Configurações de região atualizadas';

  @override
  String get cancel => 'Cancelar';

  @override
  String get detectFromGps => 'Detectar pela localização atual';

  @override
  String get setRegionPrompt => 'Configure sua área residencial';

  @override
  String get regionOptimizationDescription =>
      'Otimize os dias de coleta e regras de separação para sua área.';

  @override
  String get pleaseSelect => 'Selecione';

  @override
  String get settingsCanChangeLater =>
      'Você pode alterar as configurações posteriormente na tela de Configurações';

  @override
  String get gpsResult => 'Resultado da Detecção GPS';

  @override
  String get gpsRegionDetected => 'A seguinte região foi detectada:';

  @override
  String get setThisRegion => 'Usar esta região';

  @override
  String get selectImage => 'Selecione uma imagem';

  @override
  String get takePhoto => 'Tirar Foto';

  @override
  String get chooseFromGallery => 'Escolher da Galeria';

  @override
  String get realtimeCamera => 'Câmera em Tempo Real';

  @override
  String get noCameraAvailable => 'Nenhuma câmera disponível neste dispositivo';

  @override
  String get send => 'Enviar';

  @override
  String get redo => 'Refazer';

  @override
  String get uploading => 'Enviando...';

  @override
  String get uploadComplete => 'Upload concluído';

  @override
  String get imageSentSuccess => 'Imagem enviada com sucesso';

  @override
  String get resend => 'Reenviar';

  @override
  String get errorOccurred => 'Ocorreu um erro';

  @override
  String get municipality => 'Município';

  @override
  String get district => 'Distrito';

  @override
  String get city => 'Cidade';

  @override
  String get eveningNotification => 'Notificação noturna';

  @override
  String get morningNotification => 'Notificação matinal';

  @override
  String get addDistrict => 'Adicionar Distrito';

  @override
  String get districtListLoadError => 'Falha ao carregar lista de distritos';

  @override
  String get inUse => 'Ativo';

  @override
  String get deleteDistrict => 'Excluir Distrito';

  @override
  String deleteDistrictConfirm(String label) {
    return 'Excluir \"$label\"?';
  }

  @override
  String get delete => 'Excluir';

  @override
  String get addDistrictDialogTitle => 'Adicionar Distrito';

  @override
  String get addDistrictDescription =>
      'Digite um rótulo para o novo distrito.\nEm seguida, selecione um município e distrito.';

  @override
  String get label => 'Rótulo';

  @override
  String get labelHint => 'ex: Trabalho, Casa dos pais';

  @override
  String get labelRequired => 'Digite um rótulo';

  @override
  String get next => 'Próximo';

  @override
  String get reminderLoadError => 'Falha ao carregar configurações de lembrete';

  @override
  String get regionSettingLabel => 'Configurações de Região';

  @override
  String districtCount(int count) {
    return '$count/5';
  }
}
