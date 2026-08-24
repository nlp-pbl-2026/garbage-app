import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/waste_guide_service.dart';
import 'package:garbage_app/widgets/search_pipeline_view.dart';

void main() {
  for (final size in [const Size(390, 844), const Size(900, 700)]) {
    testWidgets('pipeline renders without overflow at ${size.width}px',
        (tester) async {
      await tester.binding.setSurfaceSize(size);
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: SearchPipelineView(
                  stage: SearchPipelineStage.classifying,
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 500));

      expect(find.text('言い換えAI'), findsOneWidget);
      expect(find.text('Bedrock KB'), findsOneWidget);
      final pipelineHeight =
          tester.getSize(find.byKey(const Key('search-pipeline-row'))).height;
      expect(pipelineHeight, size.width < 620 ? 72 : 106);
      expect(tester.takeException(), isNull);
    });
  }

  for (final brightness in Brightness.values) {
    testWidgets('pipeline text uses readable $brightness theme colors',
        (tester) async {
      final scheme = ColorScheme.fromSeed(
        seedColor: const Color(0xFF1F6B4F),
        brightness: brightness,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(colorScheme: scheme, useMaterial3: true),
          home: const Scaffold(
            body: SizedBox(
              width: 390,
              child: SearchPipelineView(stage: SearchPipelineStage.idle),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      final agentName = tester.widget<Text>(find.text('言い換えAI'));
      final technology = tester.widget<Text>(find.text('Bedrock KB'));
      expect(agentName.style?.color, scheme.onSurface);
      expect(agentName.style?.fontSize, 10);
      expect(technology.style?.color, scheme.onSurfaceVariant);
      expect(technology.style?.fontSize, 8.5);
      expect(tester.takeException(), isNull);
    });
  }
}
