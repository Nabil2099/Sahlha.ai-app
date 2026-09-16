import '../../../core/theme/sahlha_spacing.dart';
import 'widgets/learning_playground.dart';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/audio/audio_service.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../data/student_repository.dart';
import '../domain/skill_models.dart';
import 'journey_presentation.dart';
import 'widgets/learning_journey.dart' show StudentCanvas;
import 'widgets/help_me_sheet.dart';
import 'widgets/skill_media.dart'
    show LessonSkeleton, ReadAloudButton, SkillVisualCard;

/// One skill at a time: short explanation, key idea, one primary action,
/// and a single "Help me" entry point.
class SkillLessonScreen extends ConsumerWidget {
  const SkillLessonScreen({
    super.key,
    required this.skillId,
    required this.materialId,
    this.classroomId,
    this.supplementary = false,
  });

  final String skillId;
  final String materialId;
  final String? classroomId;
  final bool supplementary;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // A deep link without its material scope can never resolve server-side:
    // fail locally with a way back instead of firing a doomed request.
    if (materialId.isEmpty) {
      return Scaffold(
        appBar: SahlhaAppBar(
          title: 'A little understanding',
          onBack: () => context.go(
            learningLocation(
              classroomId: classroomId,
              supplementary: supplementary,
            ),
          ),
        ),
        body: StudentCanvas(
          child: ErrorState(
            message: "We couldn't open this lesson.",
            onRetry: () => context.go(
              learningLocation(
                classroomId: classroomId,
                supplementary: supplementary,
              ),
            ),
          ),
        ),
      );
    }
    final bundleProvider = studentSkillBundleProvider(
      skillId: skillId,
      materialId: materialId,
      classroomId: classroomId,
      supplementary: supplementary,
    );
    final bundle = ref.watch(bundleProvider);
    void back() {
      if (context.canPop()) {
        context.pop();
      } else {
        context.go(
          learningLocation(
            classroomId: classroomId,
            supplementary: supplementary,
          ),
        );
      }
    }

    return Scaffold(
      appBar: SahlhaAppBar(
        title: studentTitle(bundle.asData?.value.name ?? 'Your lesson'),
        onBack: back,
      ),
      body: StudentCanvas(
        child: bundle.when(
          loading: () => const LessonSkeleton(),
          error: (_, _) => ErrorState(
            message: "We couldn't open this lesson.",
            onRetry: () => ref.invalidate(bundleProvider),
          ),
          data: (skill) => _LessonReading(
            key: ValueKey('$materialId:$skillId'),
            skill: skill,
            audioUrl: ref
                .read(studentRepositoryProvider)
                .skillAudioUrl(
                  skillId: skillId,
                  materialId: materialId,
                  classroomId: classroomId,
                  supplementary: supplementary,
                ),
            skillId: skillId,
            materialId: materialId,
            classroomId: classroomId,
            supplementary: supplementary,
            help: () => _openHelp(context, ref, skill),
            example: () => ref
                .read(studentRepositoryProvider)
                .skillHelp(
                  skillId: skillId,
                  materialId: materialId,
                  classroomId: classroomId,
                  supplementary: supplementary,
                  kind: 'example',
                ),
            showVisual: () => _showVisual(context, hasImage: skill.hasImage),
            continueLearning: () {
              if (skill.exerciseReady) {
                context.push(
                  practiceLocation(
                    materialId: materialId,
                    skillId: skillId,
                    classroomId: classroomId,
                    supplementary: supplementary,
                  ),
                );
              } else {
                context.go(
                  learningLocation(
                    classroomId: classroomId,
                    supplementary: supplementary,
                  ),
                );
              }
            },
          ),
        ),
      ),
    );
  }

  Future<void> _openHelp(
    BuildContext context,
    WidgetRef ref,
    SkillBundle skill,
  ) async {
    final kind = await showSahlhaSheet<String>(
      context,
      HelpMeSheet(order: skill.helpOrder),
    );
    if (kind != null && context.mounted) {
      await _showHelp(context, ref, kind, hasImage: skill.hasImage);
    }
  }

  /// "Show visually" surfaces the same skill visual used in the lesson,
  /// or a calm note when the backend has no picture for this skill.
  void _showVisual(BuildContext context, {required bool hasImage}) {
    final text = Theme.of(context).textTheme;
    showSahlhaSheet<void>(
      context,
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('A picture for this skill', style: text.titleLarge),
          const SizedBox(height: SahlhaSpacing.md),
          SkillVisualCard(
            skillId: skillId,
            materialId: materialId,
            classroomId: classroomId,
            supplementary: supplementary,
          ),
        ],
      ),
    );
  }

  Future<void> _showHelp(
    BuildContext context,
    WidgetRef ref,
    String kind, {
    required bool hasImage,
  }) async {
    if (kind == 'read_aloud') {
      final url = ref
          .read(studentRepositoryProvider)
          .skillAudioUrl(
            skillId: skillId,
            materialId: materialId,
            classroomId: classroomId,
            supplementary: supplementary,
          );
      final err = await ref.read(audioServiceProvider).playUrl(url);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(err ?? 'Playing your lesson…'),
            duration: const Duration(seconds: 2),
          ),
        );
      }
      return;
    }
    if (kind == 'visual') {
      if (!context.mounted) return;
      _showVisual(context, hasImage: hasImage);
      return;
    }
    if (!context.mounted) return;
    showSahlhaSheet<void>(
      context,
      FutureBuilder<SkillHelp>(
        future: ref
            .read(studentRepositoryProvider)
            .skillHelp(
              skillId: skillId,
              materialId: materialId,
              kind: kind,
              classroomId: classroomId,
              supplementary: supplementary,
            ),
        builder: (ctx, snap) {
          final text = Theme.of(ctx).textTheme;
          if (snap.connectionState == ConnectionState.waiting) {
            return const Padding(
              padding: EdgeInsets.all(24),
              child: LoadingState(message: 'Preparing help…'),
            );
          }
          if (snap.hasError || snap.data == null) {
            return Padding(
              padding: const EdgeInsets.all(8),
              child: Text(
                'Help is unavailable right now. Try again soon.',
                style: text.bodyMedium,
              ),
            );
          }
          final help = snap.data!;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(cleanStudentText(help.title), style: text.titleLarge),
              const SizedBox(height: SahlhaSpacing.sm),
              if (help.steps.isNotEmpty)
                ...help.steps.map(
                  (s) => Padding(
                    padding: const EdgeInsets.only(bottom: SahlhaSpacing.sm),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.arrow_right, color: SahlhaColors.teal),
                        Expanded(
                          child: Text(
                            cleanStudentText(s),
                            style: text.bodyMedium,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              if (help.steps.isEmpty)
                Text(cleanStudentText(help.body), style: text.bodyLarge),
              if (help.keyConcepts.isNotEmpty) ...[
                const SizedBox(height: SahlhaSpacing.md),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: help.keyConcepts
                      .map(
                        (c) => Chip(
                          label: Text(cleanStudentText(c)),
                          backgroundColor: SahlhaColors.tealSoft,
                          side: BorderSide.none,
                        ),
                      )
                      .toList(),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _LessonReading extends StatefulWidget {
  const _LessonReading({
    super.key,
    required this.skill,
    required this.audioUrl,
    required this.skillId,
    required this.materialId,
    this.classroomId,
    this.supplementary = false,
    required this.help,
    required this.example,
    required this.showVisual,
    required this.continueLearning,
  });
  final SkillBundle skill;
  final String audioUrl;
  final String skillId;
  final String materialId;
  final String? classroomId;
  final bool supplementary;
  final VoidCallback help, showVisual, continueLearning;
  final Future<SkillHelp> Function() example;
  @override
  State<_LessonReading> createState() => _LessonReadingState();
}

class _LessonReadingState extends State<_LessonReading> {
  int _section = 0;
  bool _examples = false;
  Future<SkillHelp>? _example;
  final _scroll = ScrollController();
  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _showExamples() => setState(() {
    _examples = true;
    _example ??= widget.example();
  });
  @override
  Widget build(BuildContext context) {
    final skill = widget.skill;
    final sections = lessonSections(
      skill.explanation.isEmpty ? skill.description : skill.explanation,
    );
    final chunks = sections.isEmpty
        ? ['Your teacher is preparing this explanation.']
        : sections;
    final index = _section.clamp(0, chunks.length - 1);
    final last = index == chunks.length - 1;
    final text = Theme.of(context).textTheme;
    final audio = ReadAloudButton(
      key: ValueKey('audio:${widget.materialId}:${widget.skillId}'),
      skillId: widget.skillId,
      materialId: widget.materialId,
      classroomId: widget.classroomId,
      supplementary: widget.supplementary,
    );
    final audioFirst = skill.helpOrder.indexOf('read_aloud') == 0;
    return SafeArea(
      child: Column(
        children: [
          Expanded(
            child: ListView(
              controller: _scroll,
              padding: const EdgeInsets.fromLTRB(22, 8, 22, 28),
              children: [
                Row(
                  children: [
                    Expanded(child: Text(skill.subject, style: text.bodySmall)),
                    Text(
                      'Step ${skill.position}/${skill.total}',
                      style: text.bodySmall,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextButton(
                        onPressed: () => setState(() => _examples = false),
                        child: Text(
                          'Learn',
                          style: TextStyle(
                            color: !_examples
                                ? SahlhaColors.tealDark
                                : SahlhaColors.muted,
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      child: TextButton(
                        onPressed: _showExamples,
                        child: Text(
                          'Examples',
                          style: TextStyle(
                            color: _examples
                                ? SahlhaColors.tealDark
                                : SahlhaColors.muted,
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      child: TextButton(
                        onPressed: skill.exerciseReady
                            ? widget.continueLearning
                            : null,
                        child: const Text('Practice'),
                      ),
                    ),
                  ],
                ),
                const Divider(height: 1),
                const SizedBox(height: 18),
                LearningPlayground(
                  skill: skill,
                  audioUrl: widget.audioUrl,
                  subject: skill.subject,
                ),
                const SizedBox(height: 18),
                if (audioFirst) ...[audio, const SizedBox(height: 18)],
                if (_examples)
                  FutureBuilder<SkillHelp>(
                    future: _example,
                    builder: (context, snapshot) {
                      if (snapshot.hasError) {
                        return Column(
                          children: [
                            const Text('The example is unavailable right now.'),
                            TextButton(
                              onPressed: () =>
                                  setState(() => _example = widget.example()),
                              child: const Text('Try again'),
                            ),
                          ],
                        );
                      }
                      if (!snapshot.hasData) {
                        return const LoadingState(
                          message: 'Preparing your example...',
                        );
                      }
                      final example = snapshot.data!;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('An example', style: text.titleLarge),
                          const SizedBox(height: 8),
                          for (final chunk in lessonSections(example.body))
                            Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Text(chunk),
                            ),
                          for (final step in example.steps)
                            ListTile(title: Text(cleanStudentText(step))),
                        ],
                      );
                    },
                  )
                else ...[
                  Text(
                    index == 0 ? 'The idea' : 'A closer look',
                    style: text.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    chunks[index],
                    style: text.bodyLarge?.copyWith(height: 1.6),
                  ),
                  if (chunks.length > 1)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Text(
                        'Part ${index + 1} of ${chunks.length}',
                        style: text.bodySmall,
                      ),
                    ),
                ],
                const SizedBox(height: 18),
                if (!audioFirst) ...[audio, const SizedBox(height: 18)],
                ExpansionTile(
                  title: const Text('Explore the lesson diagram'),
                  children: [
                    SkillVisualCard(
                      skillId: widget.skillId,
                      materialId: widget.materialId,
                      classroomId: widget.classroomId,
                      supplementary: widget.supplementary,
                    ),
                  ],
                ),
                TextButton.icon(
                  onPressed: widget.help,
                  icon: const Icon(Icons.lightbulb_outline_rounded),
                  label: const Text('Help me'),
                ),
                if (index > 0 && !_examples)
                  TextButton(
                    onPressed: () {
                      setState(() => _section--);
                      _scroll.jumpTo(0);
                    },
                    child: const Text('Read the previous part'),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(22, 10, 22, 16),
            child: SahlhaPrimaryButton(
              label: _examples
                  ? (skill.exerciseReady ? 'Next: Practice' : 'Back to my path')
                  : last
                  ? 'Next: Examples'
                  : 'Continue reading',
              onPressed: _examples
                  ? widget.continueLearning
                  : last
                  ? _showExamples
                  : () {
                      setState(() => _section++);
                      _scroll.jumpTo(0);
                    },
            ),
          ),
        ],
      ),
    );
  }
}
