import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/providers/theme_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('saved dark mode remains valid, and system mode can be saved again',
      () async {
    SharedPreferences.setMockInitialValues({'dark_mode': 'dark'});
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container.read(themeModeProvider);
    await Future<void>.delayed(Duration.zero);

    expect(container.read(themeModeProvider), ThemeMode.dark);
    await container
        .read(themeModeProvider.notifier)
        .setThemeMode(ThemeMode.system);
    expect(container.read(themeModeProvider), ThemeMode.system);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('dark_mode'), 'system');
  });
}
