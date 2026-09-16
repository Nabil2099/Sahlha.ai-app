import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/audio/audio_service.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../data/student_repository.dart';
import '../domain/skill_models.dart';
import 'journey_presentation.dart';
import 'widgets/learning_journey.dart'
    show StudentCanvas, JourneyEyebrow, LearningMark;
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
      appBar: SahlhaAppBar(title: 'A little understanding', onBack: back),
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
            skillId: skillId,
            materialId: materialId,
            classroomId: classroomId,
            supplementary: supplementary,
            help: () => _openHelp(context, ref, skill),
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
    final kind = await showSahlhaSheet<String>(context, const HelpMeSheet());
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
    required this.skillId,
    required this.materialId,
    this.classroomId,
    this.supplementary = false,
    required this.help,
    required this.showVisual,
    required this.continueLearning,
  });
  final SkillBundle skill;
  final String skillId;
  final String materialId;
  final String? classroomId;
  final bool supplementary;
  final VoidCallback help, showVisual, continueLearning;
  @override
  State<_LessonReading> createState() => _LessonReadingState();
}

class _LessonReadingState extends State<_LessonReading> {
  int _section = 0;
  final _scroll = ScrollController();
  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final skill = widget.skill;
    final sections = lessonSections(
      skill.explanation.isEmpty ? skill.description : skill.explanation,
    );
    final chunks = sections.isEmpty
        ? [
            'Your teacher is preparing this explanation. You can return to your path for another step.',
          ]
        : sections;
    final index = _section.clamp(0, chunks.length - 1);
    final last = index == chunks.length - 1;
    final text = Theme.of(context).textTheme;
    return SafeArea(
      child: ListView(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Step ${skill.position} of ${skill.total < 1 ? 1 : skill.total}',
                ),
              ),
              Text(
                '${index + 1} / ${chunks.length}',
                semanticsLabel:
                    'Reading section ${index + 1} of ${chunks.length}',
              ),
            ],
          ),
          const SizedBox(height: 12),
          SahlhaProgressBar(value: (index + 1) / chunks.length),
          const SizedBox(height: 24),
          Text(
            studentTitle(
              skill.name,
              context: '${skill.description} ${skill.explanation}',
            ),
            style: text.headlineMedium?.copyWith(
              height: 1.2,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: SahlhaColors.surfaceRaised,
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: SahlhaColors.borderSubtle),
              boxShadow: SahlhaShadows.soft,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const LearningMark(size: 42),
                    const SizedBox(width: 12),
                    Expanded(
                      child: JourneyEyebrow(
                        index == 0 ? 'THE IDEA' : 'A CLOSER LOOK',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Text(
                  chunks[index],
                  style: text.bodyLarge?.copyWith(
                    height: 1.75,
                    color: SahlhaColors.ink,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerLeft,
            child: ReadAloudButton(
              key: ValueKey('audio:${widget.materialId}:${widget.skillId}'),
              skillId: widget.skillId,
              materialId: widget.materialId,
              classroomId: widget.classroomId,
              supplementary: widget.supplementary,
            ),
          ),
          if (index == 0) ...[
            const SizedBox(height: 18),
            SkillVisualCard(
              skillId: widget.skillId,
              materialId: widget.materialId,
              classroomId: widget.classroomId,
              supplementary: widget.supplementary,
            ),
          ],
          if (skill.keyConcepts.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: ExpansionTile(
                tilePadding: EdgeInsets.zero,
                initiallyExpanded: true,
                title: const Text('Key ideas'),
                children: skill.keyConcepts
                    .map(
                      (idea) => ListTile(
                        leading: const Icon(
                          Icons.check_rounded,
                          color: SahlhaColors.tealDark,
                        ),
                        title: Text(cleanStudentText(idea)),
                      ),
                    )
                    .toList(),
              ),
            ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: widget.help,
            icon: const Icon(Icons.lightbulb_outline_rounded),
            label: const Text('Help me'),
          ),
          const SizedBox(height: 12),
          SahlhaPrimaryButton(
            label: last
                ? (skill.exerciseReady
                      ? 'Continue to practice'
                      : 'Back to my path')
                : 'Continue',
            onPressed: last
                ? widget.continueLearning
                : () {
                    setState(() => _section++);
                    _scroll.jumpTo(0);
                  },
          ),
          if (index > 0)
            TextButton(
              onPressed: () {
                setState(() => _section--);
                _scroll.jumpTo(0);
              },
              child: const Text('Read the previous part'),
            ),
          if (last && !skill.exerciseReady)
            const Padding(
              padding: EdgeInsets.only(top: 10),
              child: Text(
                'Practice will appear when it is ready.',
                textAlign: TextAlign.center,
              ),
            ),
        ],
      ),
    );
  }
}
