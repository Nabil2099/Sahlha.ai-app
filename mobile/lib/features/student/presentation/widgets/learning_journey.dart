import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/theme/sahlha_colors.dart';
import '../journey_presentation.dart';

const _ink = SahlhaColors.ink;
const _teal = SahlhaColors.tealDark;

class StudentCanvas extends StatelessWidget {
  const StudentCanvas({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(14),
    );
    return Theme(
      data: theme.copyWith(
        filledButtonTheme: FilledButtonThemeData(
          style: theme.filledButtonTheme.style?.copyWith(
            shape: WidgetStatePropertyAll(shape),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: theme.outlinedButtonTheme.style?.copyWith(
            shape: WidgetStatePropertyAll(shape),
          ),
        ),
      ),
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 620),
          child: child,
        ),
      ),
    );
  }
}

class JourneyEyebrow extends StatelessWidget {
  const JourneyEyebrow(this.text, {super.key, this.color = _teal});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Text(
    text,
    style: Theme.of(context).textTheme.labelLarge?.copyWith(
      color: color,
      letterSpacing: 1.5,
      fontWeight: FontWeight.w700,
    ),
  );
}

class UnitProgressBar extends StatelessWidget {
  const UnitProgressBar({
    super.key,
    required this.completed,
    required this.total,
  });
  final int completed;
  final int total;
  @override
  Widget build(BuildContext context) {
    final value = total > 0 ? (completed / total).clamp(0, 1) : 0.0;
    return Semantics(
      label: '$completed of $total skills mastered',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: TweenAnimationBuilder<double>(
          tween: Tween(end: value.toDouble()),
          duration: MediaQuery.disableAnimationsOf(context)
              ? Duration.zero
              : const Duration(milliseconds: 450),
          curve: Curves.easeOut,
          builder: (context, animated, _) => LinearProgressIndicator(
            value: animated,
            minHeight: 8,
            color: _teal,
            backgroundColor: SahlhaColors.tealSoft,
          ),
        ),
      ),
    );
  }
}

/// A small original book graphic, built with Flutter shapes (no motion).
class LearningMark extends StatelessWidget {
  const LearningMark({super.key, this.size = 62});
  final double size;
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: SahlhaColors.sunSoft,
        borderRadius: BorderRadius.circular(size * .3),
      ),
      child: Icon(Icons.auto_stories_rounded, size: size * .54, color: _teal),
    ),
  );
}

class LearningUnitHeader extends StatelessWidget {
  const LearningUnitHeader({super.key, required this.unit, this.subject = ''});
  final JourneyUnit unit;

  /// Free-text subject used for the meaningful unit visual. Empty falls
  /// back to the book mark.
  final String subject;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(unit.title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 5),
        Text(
          'Unit ${unit.number} / ${unit.mastered} of ${unit.steps.length} mastered',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 10),
        UnitProgressBar(completed: unit.mastered, total: unit.steps.length),
      ],
    ),
  );
}

class CurrentSkillCard extends StatelessWidget {
  const CurrentSkillCard({
    super.key,
    required this.title,
    required this.onContinue,
    this.contextLabel = 'Continue learning',
    this.subtitle = '',
    this.started = false,
    this.onTap,
    this.progress,
    this.effort,
    this.questions = 0,
    this.minutes,
  });
  final String title, contextLabel, subtitle;
  final bool started;
  final VoidCallback onContinue;
  final VoidCallback? onTap;
  final double? progress;
  final String? effort;
  final int questions;
  final int? minutes;
  @override
  Widget build(BuildContext context) => Material(
    color: const Color(0xFFE5F6F3),
    borderRadius: BorderRadius.circular(22),
    child: InkWell(
      onTap: onTap ?? onContinue,
      borderRadius: BorderRadius.circular(22),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    contextLabel,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                const Icon(
                  Icons.subdirectory_arrow_left,
                  size: 18,
                  color: _teal,
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: const Color(0xFF009D98),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: const Icon(
                    Icons.auto_stories_outlined,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      if (subtitle.isNotEmpty)
                        Text(
                          subtitle,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.play_circle_fill, color: _teal, size: 32),
              ],
            ),
            if (minutes != null || questions > 0) ...[
              const SizedBox(height: 14),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  if (minutes != null)
                    _MetaPill(Icons.headphones_outlined, '~$minutes min'),
                  if (questions > 0)
                    _MetaPill(
                      Icons.assignment_outlined,
                      '$questions questions',
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    ),
  );
}

class _MetaPill extends StatelessWidget {
  const _MetaPill(this.icon, this.label);
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .85),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 15, color: _teal),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );
}

class SkillStatusIndicator extends StatelessWidget {
  const SkillStatusIndicator({super.key, required this.state});
  final JourneyState state;
  @override
  Widget build(BuildContext context) => Text(switch (state) {
    JourneyState.completed => 'Completed',
    JourneyState.current => 'Your next step',
    JourneyState.available => 'Explore',
    JourneyState.locked => 'Coming later',
  }, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: _teal));
}

class LearningPathNode extends StatelessWidget {
  const LearningPathNode({
    super.key,
    required this.step,
    required this.onTap,
    this.selected = false,
  });
  final JourneyStep step;
  final VoidCallback? onTap;

  /// Presentation-only emphasis. Independent from progression state:
  /// a completed node can be completed + selected, a locked one locked +
  /// selected. Selecting never changes backend mastery.
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final completed = step.state == JourneyState.completed;
    final locked = step.state == JourneyState.locked;
    final current = step.state == JourneyState.current;
    return Semantics(
      selected: selected,
      button: true,
      label: '${step.title}, ${step.state.name}',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: AnimatedContainer(
          duration: MediaQuery.disableAnimationsOf(context)
              ? Duration.zero
              : const Duration(milliseconds: 280),
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
          decoration: BoxDecoration(
            color: selected ? Colors.white : Colors.transparent,
            borderRadius: BorderRadius.circular(20),
            boxShadow: selected ? SahlhaShadows.soft : null,
          ),
          child: Row(
            children: [
              AnimatedContainer(
                duration: MediaQuery.disableAnimationsOf(context)
                    ? Duration.zero
                    : const Duration(milliseconds: 300),
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: completed
                      ? const Color(0xFF009F98)
                      : current
                      ? SahlhaColors.sun
                      : const Color(0xFFF4F5F6),
                  border: Border.all(
                    color: selected || current
                        ? _teal
                        : completed
                        ? const Color(0xFFBDEAE1)
                        : const Color(0xFFDEE2E5),
                    width: 2,
                  ),
                ),
                child: Icon(
                  completed
                      ? Icons.check_rounded
                      : locked
                      ? Icons.lock_outline_rounded
                      : Icons.lightbulb_outline_rounded,
                  color: completed
                      ? Colors.white
                      : current
                      ? const Color(0xFF956300)
                      : _ink,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      step.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    SkillStatusIndicator(state: step.state),
                    if (current && step.skill.practiceQuestions > 0)
                      Text(
                        '${step.skill.practiceQuestions} questions',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Detail card for the currently selected path step. The content follows
/// the step's progression state; selection itself never changes mastery.
class LearningPathSkillBlock extends StatelessWidget {
  const LearningPathSkillBlock({
    super.key,
    required this.step,
    required this.prerequisiteTitle,
    required this.onPrimary,
  });

  final JourneyStep step;

  /// Title of the step to finish first (locked steps). Empty when unknown.
  final String prerequisiteTitle;

  /// Opens the lesson (completed/current/available). Null for locked steps.
  final VoidCallback? onPrimary;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final (eyebrow, message, cta, ctaIcon) = switch (step.state) {
      JourneyState.completed => (
        'COMPLETED',
        'You\u2019ve completed this skill.',
        'Review skill',
        Icons.refresh_rounded,
      ),
      JourneyState.current => (
        'YOUR NEXT STEP',
        'One small step. Take it at your pace.',
        'Continue',
        Icons.arrow_forward_rounded,
      ),
      JourneyState.available => (
        'READY WHEN YOU ARE',
        'Build on what you have learned.',
        'Start skill',
        Icons.arrow_forward_rounded,
      ),
      JourneyState.locked => (
        'COMING UP',
        prerequisiteTitle.isEmpty
            ? 'Finish the earlier steps to open this one.'
            : 'Complete \u201C$prerequisiteTitle\u201D first.',
        null,
        Icons.lock_outline_rounded,
      ),
    };
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(left: 64),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SahlhaColors.surfaceRaised,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: SahlhaColors.tealSoft),
        boxShadow: SahlhaShadows.soft,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: JourneyEyebrow(eyebrow)),
              Icon(
                switch (step.state) {
                  JourneyState.completed => Icons.check_circle_rounded,
                  JourneyState.locked => Icons.lock_outline_rounded,
                  _ => Icons.play_circle_outline_rounded,
                },
                color: SahlhaColors.tealDark,
                size: 26,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            message,
            style: text.bodyMedium?.copyWith(
              color: SahlhaColors.muted,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 10),
          if (cta != null)
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: onPrimary,
                icon: Icon(ctaIcon, size: 20),
                label: Text(cta),
                style: FilledButton.styleFrom(minimumSize: const Size(48, 48)),
              ),
            )
          else
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: null,
                icon: Icon(ctaIcon, size: 20),
                label: const Text('Locked for now'),
              ),
            ),
        ],
      ),
    );
  }
}

class LearningPathConnector extends StatelessWidget {
  const LearningPathConnector({
    super.key,
    required this.from,
    required this.to,
    required this.state,
  });
  final double from;
  final double to;
  final JourneyState state;
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: SizedBox(
      height: 20,
      width: double.infinity,
      child: TweenAnimationBuilder<Color?>(
        tween: ColorTween(
          end: state == JourneyState.completed
              ? _teal
              : const Color(0xFFDDD8CE),
        ),
        duration: MediaQuery.disableAnimationsOf(context)
            ? Duration.zero
            : const Duration(milliseconds: 350),
        builder: (_, color, _) =>
            CustomPaint(painter: _ConnectorPainter(from, to, color ?? _teal)),
      ),
    ),
  );
}

class _ConnectorPainter extends CustomPainter {
  const _ConnectorPainter(this.from, this.to, this.color);
  final double from, to;
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    const start = 33.0;
    const end = 33.0;
    final path = Path()
      ..moveTo(start, 0)
      ..cubicTo(
        start,
        size.height * .5,
        end,
        size.height * .5,
        end,
        size.height,
      );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 3
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_ConnectorPainter old) =>
      old.from != from || old.to != to || old.color != color;
}

/// A Quick Check on the path: a short, low-pressure revisit of recent
/// steps once they have real attempts. Locked (null [onTap]) until then.
class CheckpointNode extends StatelessWidget {
  const CheckpointNode({
    super.key,
    this.onTap,
    this.title = 'Quick check',
    this.subtitle = 'A short pause to remember.',
  });
  final VoidCallback? onTap;
  final String title, subtitle;
  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration: MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 300),
    margin: const EdgeInsets.symmetric(vertical: 16),
    decoration: BoxDecoration(
      color: onTap == null ? const Color(0xFFF4F1FA) : const Color(0xFFECE4FF),
      borderRadius: BorderRadius.circular(22),
    ),
    child: ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      leading: Icon(
        onTap == null ? Icons.lock_outline_rounded : Icons.flag_outlined,
        color: const Color(0xFF7858D8),
      ),
      title: Text(title, style: Theme.of(context).textTheme.titleMedium),
      subtitle: Text(subtitle),
      trailing: onTap == null
          ? null
          : const Icon(Icons.arrow_forward_rounded, color: Color(0xFF7858D8)),
      onTap: onTap,
    ),
  );
}

class MasteryNode extends StatelessWidget {
  const MasteryNode({
    super.key,
    required this.ready,
    this.onTap,
    this.mastered = 0,
    this.total = 0,
  });
  final bool ready;
  final VoidCallback? onTap;

  /// Unit progress shown under the title (0/0 hides the line).
  final int mastered;
  final int total;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(22),
    margin: const EdgeInsets.only(top: 20),
    decoration: BoxDecoration(
      color: ready ? SahlhaColors.sunSoft : SahlhaColors.surfaceRaised,
      borderRadius: BorderRadius.circular(26),
      border: Border.all(color: SahlhaColors.borderSubtle),
      boxShadow: SahlhaShadows.soft,
    ),
    child: Column(
      children: [
        Icon(
          ready ? Icons.workspace_premium_outlined : Icons.lock_outline_rounded,
          color: _teal,
          size: 34,
        ),
        const SizedBox(height: 10),
        const JourneyEyebrow('MASTERY CHECK'),
        const SizedBox(height: 8),
        Text(
          'Bring it all together',
          style: Theme.of(context).textTheme.titleLarge,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          ready
              ? 'Revisit this unit in one practice session.'
              : total > 0
              ? '$mastered of $total skills at mastery — keep going one step at a time.'
              : 'Ready when these skills are mastered and practice is prepared.',
          textAlign: TextAlign.center,
        ),
        if (ready) ...[
          const SizedBox(height: 14),
          OutlinedButton(
            onPressed: onTap,
            child: const Text('Review this unit'),
          ),
        ],
      ],
    ),
  );
}

class LearningPath extends StatefulWidget {
  const LearningPath({
    super.key,
    required this.unit,
    required this.openSkill,
    required this.openCheckpoint,
    required this.openMastery,
  });
  final JourneyUnit unit;
  final ValueChanged<JourneyStep> openSkill, openCheckpoint;
  final VoidCallback openMastery;
  @override
  State<LearningPath> createState() => _LearningPathState();
}

class _LearningPathState extends State<LearningPath> {
  bool _earlier = false;
  int _extra = 0;

  /// Presentation-only selection. Defaults to the backend-recommended
  /// skill; tapping any node moves the detail block there. Selecting
  /// never completes, unlocks, or resets anything server-side.
  String? _selectedId;
  final _blockKey = GlobalKey();

  /// First step worth showing in the detail block when the backend names no
  /// recommended skill (e.g. everything mastered): the first open step,
  /// else the first step, so the block is never empty.
  String? _defaultSelection(JourneyUnit unit) {
    if (unit.steps.isEmpty) return null;
    return unit.current?.skill.skillId ??
        unit.steps
            .where((s) => s.state != JourneyState.locked)
            .firstOrNull
            ?.skill
            .skillId ??
        unit.steps.first.skill.skillId;
  }

  @override
  void initState() {
    super.initState();
    _selectedId = _defaultSelection(widget.unit);
  }

  @override
  void didUpdateWidget(LearningPath oldWidget) {
    super.didUpdateWidget(oldWidget);
    final oldCurrent = oldWidget.unit.current?.skill.skillId;
    final newCurrent = widget.unit.current?.skill.skillId;
    final stillThere = widget.unit.steps.any(
      (s) => s.skill.skillId == _selectedId,
    );
    if (oldWidget.unit.source.materialId != widget.unit.source.materialId ||
        oldCurrent != newCurrent ||
        !stillThere) {
      _earlier = false;
      _extra = 0;
      // Backend progress changed (e.g. a skill was mastered): follow the
      // new recommendation instead of clinging to a stale selection.
      // An explicit user selection survives plain data refreshes above.
      _selectedId = _defaultSelection(widget.unit);
    }
  }

  double _offset(JourneyStep step) => 0;

  void _select(JourneyStep step) {
    if (_selectedId == step.skill.skillId) return;
    HapticFeedback.selectionClick();
    setState(() => _selectedId = step.skill.skillId);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final context = _blockKey.currentContext;
      if (context == null || !context.mounted) return;
      try {
        Scrollable.ensureVisible(
          context,
          duration: MediaQuery.disableAnimationsOf(context)
              ? Duration.zero
              : const Duration(milliseconds: 250),
          curve: Curves.easeOut,
          alignment: 0.3,
        );
      } catch (_) {
        // Scrolling is a nicety; the block is already visible in-flow.
      }
    });
  }

  /// Nearest earlier step that is not completed yet, for locked explanations.
  String _prerequisiteTitle(JourneyUnit unit, JourneyStep step) {
    for (var i = step.index - 1; i >= 0; i--) {
      final earlier = unit.steps[i];
      if (earlier.state != JourneyState.completed) return earlier.title;
    }
    return '';
  }

  @override
  Widget build(BuildContext context) {
    final unit = widget.unit;
    final steps = unit.steps;
    final selected = steps
        .where((s) => s.skill.skillId == _selectedId)
        .firstOrNull;
    final focus = unit.current?.index ?? 0;
    final start = _earlier ? 0 : (focus - 1).clamp(0, steps.length);
    final end = (focus + 4 + _extra).clamp(0, steps.length);
    final children = <Widget>[];
    var bridgeFromCenter = false;
    JourneyStep? previous = start > 0 ? steps[start - 1] : null;
    for (var i = start; i < end; i++) {
      final step = steps[i];
      final off = _offset(step);
      if (previous != null) {
        // The connector either links two neighbouring nodes, or runs
        // from the selected detail block back onto the journey.
        children.add(
          LearningPathConnector(
            from: bridgeFromCenter ? 0 : _offset(previous),
            to: off,
            state: previous.state,
          ),
        );
      }
      bridgeFromCenter = false;
      children.add(
        Align(
          alignment: Alignment(off, 0),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 620),
            child: LearningPathNode(
              step: step,
              selected: selected?.skill.skillId == step.skill.skillId,
              onTap: () => _select(step),
            ),
          ),
        ),
      );
      if (selected?.skill.skillId == step.skill.skillId) {
        // The detail block lives ON the path: a connector runs into it
        // and another one carries the journey onwards.
        children.add(
          LearningPathConnector(from: off, to: 0, state: step.state),
        );
        // NOTE: no AnimatedSize here on purpose — combining it with the
        // scroll-into-view below mutates layout mid-frame and throws.
        // The fade keeps the change gentle.
        children.add(
          AnimatedSwitcher(
            key: _blockKey,
            duration: MediaQuery.disableAnimationsOf(context)
                ? Duration.zero
                : const Duration(milliseconds: 180),
            child: LearningPathSkillBlock(
              key: ValueKey('block:${step.skill.skillId}'),
              step: step,
              prerequisiteTitle: _prerequisiteTitle(unit, step),
              onPrimary: step.state == JourneyState.locked
                  ? null
                  : () => widget.openSkill(step),
            ),
          ),
        );
        bridgeFromCenter = true;
      }
      previous = step;
      if ((i + 1) % 3 == 0 && i + 1 < steps.length) {
        children.add(
          CheckpointNode(
            subtitle: unit.checkpointAfter(i + 1) == null
                ? 'After practicing these steps.'
                : 'Mix your practiced skills.',
            onTap: unit.checkpointAfter(i + 1) == null
                ? null
                : () => widget.openCheckpoint(unit.checkpointAfter(i + 1)!),
          ),
        );
      }
    }
    if (bridgeFromCenter) {
      children.add(
        LearningPathConnector(
          from: 0,
          to: 0,
          state: selected?.state ?? JourneyState.available,
        ),
      );
    }
    return Column(
      children: [
        if (start > 0)
          TextButton(
            onPressed: () => setState(() => _earlier = true),
            child: Text('See $start earlier ${start == 1 ? 'step' : 'steps'}'),
          ),
        const SizedBox(height: 16),
        ...children,
        if (end < steps.length)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: TextButton(
              onPressed: () => setState(() => _extra += 3),
              child: const Text('See what comes next'),
            ),
          ),
        MasteryNode(
          ready: unit.masteryReady,
          onTap: widget.openMastery,
          mastered: unit.mastered,
          total: unit.steps.length,
        ),
      ],
    );
  }
}

class JourneyLoading extends StatelessWidget {
  const JourneyLoading({super.key});
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Loading your learning path',
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          Container(
            height: 115,
            decoration: BoxDecoration(
              color: SahlhaColors.tealSoft,
              borderRadius: BorderRadius.circular(24),
            ),
          ),
          const SizedBox(height: 24),
          const Text('Getting your next step ready…'),
          for (var i = 0; i < 3; i++)
            Padding(
              padding: const EdgeInsets.all(18),
              child: Align(
                alignment: Alignment(i.isEven ? -.35 : .35, 0),
                child: Container(
                  width: 66,
                  height: 62,
                  decoration: BoxDecoration(
                    color: SahlhaColors.line,
                    borderRadius: BorderRadius.circular(20),
                  ),
                ),
              ),
            ),
        ],
      ),
    ),
  );
}
