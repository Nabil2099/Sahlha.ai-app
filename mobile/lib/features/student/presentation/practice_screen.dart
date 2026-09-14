import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import 'practice_controller.dart';

/// One question at a time. Large touch targets, predictable layout,
/// immediate honest feedback from the server. Celebrations only for
/// real milestones (never for a single correct answer).
class PracticeScreen extends ConsumerStatefulWidget {
  const PracticeScreen({
    super.key,
    this.classroomId,
    this.materialId,
    this.skillId,
    this.supplementary = false,
  });

  final String? classroomId;
  final String? materialId;
  final String? skillId;
  final bool supplementary;

  @override
  ConsumerState<PracticeScreen> createState() => _PracticeScreenState();
}

class _PracticeScreenState extends ConsumerState<PracticeScreen> {
  final _shortAnswer = TextEditingController();

  String? get _classroomId =>
      widget.classroomId?.isEmpty == true ? null : widget.classroomId;

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref
        .read(practiceControllerProvider.notifier)
        .start(
          classroomId: _classroomId,
          materialId: widget.materialId,
          skillId: widget.skillId,
          childScope: widget.supplementary,
        ));
  }

  @override
  void dispose() {
    _shortAnswer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(practiceControllerProvider);
    final text = Theme.of(context).textTheme;

    if (state.starting) {
      return const Scaffold(
          body: LoadingState(message: 'Preparing your practice…'));
    }
    if (state.error != null && state.questions.isEmpty) {
      return Scaffold(
        appBar: const SahlhaAppBar(title: 'Practice'),
        body: ErrorState(
          message: state.error!,
          onRetry: () => context.pop(),
        ),
      );
    }
    if (state.result != null) {
      return _ResultView(
        classroomId: _classroomId,
        materialId: widget.materialId,
        skillId: widget.skillId,
      );
    }
    if (state.submitting) {
      return const Scaffold(
          body: LoadingState(message: 'Checking your work…'));
    }
    final q = state.current;
    if (q == null) {
      return const Scaffold(body: LoadingState());
    }
    final controller = ref.read(practiceControllerProvider.notifier);
    final selected = state.answers[q.id];
    final check = state.checked[q.id];
    final isShort = q.options.isEmpty;

    return PopScope(
      canPop: true,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) controller.reset();
      },
      child: Scaffold(
        appBar: const SahlhaAppBar(title: 'Practice'),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Question ${state.index + 1} of ${state.questions.length}',
                    style: text.bodySmall
                        ?.copyWith(color: SahlhaColors.muted)),
                const SizedBox(height: SahlhaSpacing.sm),
                SahlhaProgressBar(
                    value: (state.index + 1) / state.questions.length),
                const SizedBox(height: SahlhaSpacing.xl),
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(q.question, style: text.titleLarge),
                        const SizedBox(height: SahlhaSpacing.lg),
                        if (!isShort)
                          ...List.generate(q.options.length, (i) {
                            final correctAnswer =
                                check?.correctAnswer is int
                                    ? check!.correctAnswer as int
                                    : null;
                            return Padding(
                              padding: const EdgeInsets.only(
                                  bottom: SahlhaSpacing.sm),
                              child: QuestionOptionCard(
                                label: q.options[i],
                                selected: selected == i,
                                correct: check == null
                                    ? null
                                    : (correctAnswer == i ||
                                        (check.correct && selected == i)),
                                onTap: check != null
                                    ? () {}
                                    : () => controller.answerCurrent(i),
                              ),
                            );
                          })
                        else
                          TextFormField(
                            controller: _shortAnswer,
                            enabled: check == null,
                            maxLines: 2,
                            decoration: const InputDecoration(
                                labelText: 'Your answer',
                                hintText: 'Write a short answer'),
                            onChanged: (v) => controller.answerCurrent(v),
                          ),
                        if (check != null) ...[
                          const SizedBox(height: SahlhaSpacing.md),
                          InlineFeedback(
                            correct: check.correct,
                            message: check.explanation.isNotEmpty
                                ? check.explanation
                                : (check.correct
                                    ? 'Well done. Keep going.'
                                    : 'Look at the question again, then try the next one.'),
                          ),
                        ] else if (state.supportLevel > 0) ...[
                          const SizedBox(height: SahlhaSpacing.md),
                          InlineFeedback(
                            correct: true,
                            message: state.supportLevel == 1
                                ? 'Hint: re-read the question slowly, one part at a time.'
                                : 'Keep it simple: answer what you know, then move on. Trying matters.',
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: SahlhaSpacing.md),
                if (check == null)
                  Row(
                    children: [
                      Expanded(
                        child: SahlhaSecondaryButton(
                          label: 'Hint',
                          onPressed: () =>
                              controller.requestSupportHint(),
                        ),
                      ),
                      const SizedBox(width: SahlhaSpacing.md),
                      Expanded(
                        flex: 2,
                        child: SahlhaPrimaryButton(
                          label: 'Check answer',
                          onPressed: (!isShort && selected == null) ||
                                  (isShort &&
                                      _shortAnswer.text.trim().isEmpty &&
                                      selected == null)
                              ? null
                              : () {
                                  if (isShort &&
                                      _shortAnswer.text.trim().isNotEmpty) {
                                    controller.answerCurrent(
                                        _shortAnswer.text.trim());
                                  }
                                  controller.checkCurrent();
                                },
                        ),
                      ),
                    ],
                  )
                else if (!state.isLast)
                  SahlhaPrimaryButton(
                    label: 'Next question',
                    onPressed: () {
                      _shortAnswer.clear();
                      controller.next();
                    },
                  )
                else
                  SahlhaPrimaryButton(
                    label: 'See my results',
                    onPressed: () => controller.submit(),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Result + feedback. Big celebration ONLY for real milestones
/// (skill mastered), never for a single correct answer.
class _ResultView extends ConsumerWidget {
  const _ResultView({this.classroomId, this.materialId, this.skillId});

  final String? classroomId;
  final String? materialId;
  final String? skillId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(practiceControllerProvider).result!;
    final text = Theme.of(context).textTheme;
    final masteredNow = result.masteryStates.values
        .where((s) => s == 'mastered')
        .length;
    final scorePct = (result.score * 100).round();

    return Scaffold(
      appBar: const SahlhaAppBar(title: 'Feedback'),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(SahlhaSpacing.page),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (masteredNow > 0) ...[
                Center(
                  child: Container(
                    width: 110,
                    height: 110,
                    decoration: const BoxDecoration(
                        color: SahlhaColors.sunSoft,
                        shape: BoxShape.circle),
                    child: const Icon(Icons.star,
                        size: 60, color: SahlhaColors.sun),
                  ),
                ),
                const SizedBox(height: SahlhaSpacing.lg),
                Text('Skill mastered!',
                    style: text.headlineSmall,
                    textAlign: TextAlign.center),
                Text('You did it. Steady work pays off.',
                    style: text.bodyMedium
                        ?.copyWith(color: SahlhaColors.muted),
                    textAlign: TextAlign.center),
              ] else ...[
                Center(
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: const BoxDecoration(
                        color: SahlhaColors.tealSoft,
                        shape: BoxShape.circle),
                    child: const Icon(Icons.check,
                        size: 52, color: SahlhaColors.teal),
                  ),
                ),
                const SizedBox(height: SahlhaSpacing.lg),
                Text('Practice complete.',
                    style: text.headlineSmall,
                    textAlign: TextAlign.center),
                Text(
                    scorePct >= 60
                        ? 'Good progress. Keep practicing.'
                        : 'Not yet — and that’s okay. Let’s keep practicing.',
                    style: text.bodyMedium
                        ?.copyWith(color: SahlhaColors.muted),
                    textAlign: TextAlign.center),
              ],
              const SizedBox(height: SahlhaSpacing.xl),
              SahlhaCard(
                child: Column(
                  children: [
                    Text('${result.correct} of ${result.total} correct',
                        style: text.titleLarge),
                    const SizedBox(height: SahlhaSpacing.sm),
                    SahlhaProgressBar(value: result.score),
                    const SizedBox(height: SahlhaSpacing.md),
                    ...result.results.map((r) => Padding(
                          padding: const EdgeInsets.only(
                              bottom: SahlhaSpacing.xs),
                          child: Row(
                            children: [
                              Icon(
                                  r.correct
                                      ? Icons.check_circle
                                      : Icons.cancel_outlined,
                                  size: 18,
                                  color: r.correct
                                      ? SahlhaColors.success
                                      : SahlhaColors.muted),
                              const SizedBox(width: SahlhaSpacing.sm),
                              Expanded(
                                  child: Text(r.skillId,
                                      style: text.bodySmall)),
                              SkillStatusBadge(
                                  state: result.masteryStates[r.skillId] ??
                                      'not_started'),
                            ],
                          ),
                        )),
                  ],
                ),
              ),
              const SizedBox(height: SahlhaSpacing.xl),
              SahlhaPrimaryButton(
                label: 'Back to my path',
                onPressed: () {
                  ref.read(practiceControllerProvider.notifier).reset();
                  if (classroomId != null && classroomId!.isNotEmpty) {
                    context.go('/student/learn?classroomId=$classroomId');
                  } else {
                    context.go('/student/learn');
                  }
                },
              ),
              const SizedBox(height: SahlhaSpacing.sm),
              SahlhaSecondaryButton(
                label: 'Practice again',
                onPressed: () {
                  final c =
                      ref.read(practiceControllerProvider.notifier);
                  c.reset();
                  c.start(
                    classroomId: classroomId,
                    materialId: materialId,
                    skillId: skillId,
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
