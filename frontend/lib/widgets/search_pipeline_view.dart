import 'package:flutter/material.dart';

import '../services/waste_guide_service.dart';

class SearchPipelineView extends StatefulWidget {
  final SearchPipelineStage stage;
  final bool compact;

  const SearchPipelineView({
    super.key,
    required this.stage,
    this.compact = false,
  });

  @override
  State<SearchPipelineView> createState() => _SearchPipelineViewState();
}

class _SearchPipelineViewState extends State<SearchPipelineView>
    with SingleTickerProviderStateMixin {
  late final AnimationController _motion;

  static const _steps = [
    _PipelineStep(Icons.auto_fix_high_rounded, '言い換えAI', 'Nova Lite'),
    _PipelineStep(Icons.travel_explore_rounded, '地域資料検索', 'Bedrock KB'),
    _PipelineStep(Icons.psychology_alt_rounded, '分別判定AI', 'Nova Lite'),
    _PipelineStep(Icons.event_available_rounded, '収集日照合', '清水カレンダー'),
  ];

  @override
  void initState() {
    super.initState();
    _motion = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat();
  }

  @override
  void dispose() {
    _motion.dispose();
    super.dispose();
  }

  int get _activeIndex => switch (widget.stage) {
        SearchPipelineStage.idle => -1,
        SearchPipelineStage.rewriting => 0,
        SearchPipelineStage.retrieving => 1,
        SearchPipelineStage.classifying => 2,
        SearchPipelineStage.completed => 4,
      };

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final spacious = constraints.maxWidth >= 620 && !widget.compact;
        final children = <Widget>[];
        for (var i = 0; i < _steps.length; i++) {
          final card = _AgentCard(
            step: _steps[i],
            active: i == _activeIndex ||
                (widget.stage == SearchPipelineStage.classifying && i == 3),
            complete: _activeIndex > i,
            motion: _motion,
            compact: !spacious,
          );
          children.add(Expanded(child: card));
          if (i < _steps.length - 1) {
            final transferring = _activeIndex == i + 1 ||
                (widget.stage == SearchPipelineStage.classifying && i == 2);
            children.add(
              _AnimatedConnector(
                vertical: false,
                active: transferring,
                complete: _activeIndex > i + 1,
                motion: _motion,
                compact: !spacious,
              ),
            );
          }
        }
        return Row(key: const Key('search-pipeline-row'), children: children);
      },
    );
  }
}

class _PipelineStep {
  final IconData icon;
  final String title;
  final String technology;

  const _PipelineStep(this.icon, this.title, this.technology);
}

class _AgentCard extends StatelessWidget {
  final _PipelineStep step;
  final bool active;
  final bool complete;
  final Animation<double> motion;
  final bool compact;

  const _AgentCard({
    required this.step,
    required this.active,
    required this.complete,
    required this.motion,
    required this.compact,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: motion,
      builder: (context, child) {
        final pulse =
            active ? 1 + (0.025 * (1 - (motion.value * 2 - 1).abs())) : 1.0;
        return Transform.scale(scale: pulse, child: child);
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 280),
        constraints: BoxConstraints(minHeight: compact ? 72 : 106),
        padding: EdgeInsets.symmetric(
          horizontal: compact ? 3 : 10,
          vertical: compact ? 8 : 14,
        ),
        decoration: BoxDecoration(
          color: active
              ? const Color(0xFFE2F5EA)
              : complete
                  ? const Color(0xFFF0F7F3)
                  : Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: active ? const Color(0xFF2A8A65) : const Color(0xFFDDE6E0),
            width: active ? 2 : 1,
          ),
          boxShadow: active
              ? const [
                  BoxShadow(
                    color: Color(0x302A8A65),
                    blurRadius: 18,
                    offset: Offset(0, 6),
                  ),
                ]
              : const [],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(step.icon,
                    size: compact ? 21 : 29,
                    color: active || complete
                        ? const Color(0xFF1F6B4F)
                        : const Color(0xFF829089)),
                if (complete)
                  const Positioned(
                    right: -8,
                    top: -7,
                    child: Icon(Icons.check_circle_rounded,
                        size: 16, color: Color(0xFF2A8A65)),
                  ),
              ],
            ),
            SizedBox(height: compact ? 5 : 8),
            Text(step.title,
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontWeight: FontWeight.w800, fontSize: compact ? 9 : 12)),
            SizedBox(height: compact ? 1 : 3),
            Text(step.technology,
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    fontSize: compact ? 7 : 10,
                    color: const Color(0xFF66756E))),
          ],
        ),
      ),
    );
  }
}

class _AnimatedConnector extends StatelessWidget {
  final bool vertical;
  final bool active;
  final bool complete;
  final Animation<double> motion;
  final bool compact;

  const _AnimatedConnector({
    required this.vertical,
    required this.active,
    required this.complete,
    required this.motion,
    required this.compact,
  });

  @override
  Widget build(BuildContext context) {
    final color =
        active || complete ? const Color(0xFF2A8A65) : const Color(0xFFCBD6D0);
    return SizedBox(
      width: vertical ? double.infinity : (compact ? 12 : 34),
      height: vertical ? 30 : (compact ? 72 : 106),
      child: AnimatedBuilder(
        animation: motion,
        builder: (context, _) {
          final alignment = active
              ? Alignment.lerp(
                  vertical ? Alignment.topCenter : Alignment.centerLeft,
                  vertical ? Alignment.bottomCenter : Alignment.centerRight,
                  motion.value,
                )!
              : Alignment.center;
          return Stack(
            alignment: Alignment.center,
            children: [
              Container(
                width: vertical ? 2 : double.infinity,
                height: vertical ? double.infinity : 2,
                color: color,
              ),
              Align(
                alignment: alignment,
                child: Icon(
                  vertical
                      ? Icons.arrow_downward_rounded
                      : Icons.arrow_forward_rounded,
                  size: active ? 20 : 16,
                  color: color,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
