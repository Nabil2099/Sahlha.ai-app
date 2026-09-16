import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/widgets/sahlha_widgets.dart'
    show
        SahlhaAppBar,
        SahlhaProgressBar,
        SahlhaPrimaryButton,
        ErrorState,
        EmptyState,
        LoadingState,
        InlineFeedback;
import 'practice_controller.dart';
import 'journey_presentation.dart';
import 'widgets/learning_journey.dart'
    show StudentCanvas, JourneyEyebrow, LearningMark;

class PracticeScreen extends ConsumerStatefulWidget {
  const PracticeScreen({
    super.key,
    this.classroomId,
    this.materialId,
    this.skillId,
    this.supplementary = false,
    this.mode = 'practice',
  });
  final String? classroomId, materialId, skillId;
  final bool supplementary;
  final String mode;
  @override
  ConsumerState<PracticeScreen> createState() => _PracticeScreenState();
}

class _PracticeScreenState extends ConsumerState<PracticeScreen> {
  final _answer = TextEditingController();
  final _scroll = ScrollController();
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) _start();
    });
  }

  Future<void> _start() async {
    _answer.clear();
    await ref
        .read(practiceControllerProvider.notifier)
        .start(
          classroomId: widget.classroomId,
          materialId: widget.materialId,
          skillId: widget.skillId,
          childScope: widget.supplementary,
        );
  }

  @override
  void dispose() {
    _answer.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _path() {
    context.go(
      learningLocation(
        classroomId: widget.classroomId,
        supplementary: widget.supplementary,
      ),
    );
  }

  void _back() {
    if (context.canPop()) {
      context.pop();
    } else {
      _path();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(practiceControllerProvider);
    final controller = ref.read(practiceControllerProvider.notifier);
    final text = Theme.of(context).textTheme;
    final title = widget.mode == 'mastery'
        ? 'Unit mastery check'
        : widget.mode == 'checkpoint'
        ? 'Quick practice'
        : 'A little practice';
    return Scaffold(
      appBar: SahlhaAppBar(
        title: state.result != null ? 'Your next step' : title,
        onBack: _back,
      ),
      body: StudentCanvas(
        child: SafeArea(
          child: Builder(
            builder: (context) {
              if (state.starting) {
                return const LoadingState(
                  message: 'Preparing a little practice…',
                );
              }
              if (state.error != null && state.questions.isEmpty) {
                return ErrorState(message: state.error!, onRetry: _start);
              }
              if (state.result != null) return _feedback(context, state);
              if (state.current == null) {
                return SingleChildScrollView(
                  child: EmptyState(
                    title: 'Practice is being prepared.',
                    message: 'Return to your learning path for another step.',
                    action: SahlhaPrimaryButton(
                      label: 'Back to my path',
                      onPressed: _path,
                    ),
                  ),
                );
              }
              final q = state.current!;
              final check = state.checked[q.id];
              final selected = state.answers[q.id];
              final valid =
                  selected != null &&
                  (selected is! String || selected.trim().isNotEmpty);
              return ListView(
                controller: _scroll,
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
                children: [
                  JourneyEyebrow(
                    'QUESTION ${state.index + 1} OF ${state.questions.length}',
                  ),
                  const SizedBox(height: 12),
                  SahlhaProgressBar(
                    value: (state.index + 1) / state.questions.length,
                  ),
                  const SizedBox(height: 24),
                  Container(
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(26),
                      border: Border.all(color: SahlhaColors.line),
                    ),
                    child: Text(
                      cleanStudentText(q.question),
                      style: text.titleLarge?.copyWith(height: 1.55),
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (q.options.isNotEmpty)
                    for (var i = 0; i < q.options.length; i++)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: _AnswerOption(
                          label: cleanStudentText(q.options[i]),
                          index: i,
                          selected: selected == i,
                          correct:
                              check != null &&
                              (check.correctAnswer == i ||
                                  (check.correct && selected == i)),
                          onTap: check != null || state.checking
                              ? null
                              : () => controller.answerCurrent(i),
                        ),
                      )
                  else
                    TextField(
                      controller: _answer,
                      enabled: check == null && !state.checking,
                      minLines: 2,
                      maxLines: 5,
                      decoration: const InputDecoration(
                        labelText: 'Your answer',
                        hintText: 'Write what you think',
                      ),
                      onChanged: controller.answerCurrent,
                    ),
                  if (state.error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Semantics(
                        liveRegion: true,
                        child: Text(state.error!, style: text.bodyMedium),
                      ),
                    ),
                  if (check != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Semantics(
                        liveRegion: true,
                        child: InlineFeedback(
                          correct: check.correct,
                          message: cleanStudentText(check.explanation).isEmpty
                              ? (check.correct
                                    ? 'You’ve got the idea.'
                                    : 'Keep this idea in mind for the next question.')
                              : cleanStudentText(check.explanation),
                        ),
                      ),
                    ),
                  if (state.supportLevel > 0 && check == null)
                    Container(
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: SahlhaColors.sunSoft,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Text(
                        'Read one part at a time. What is the question asking you to find?',
                      ),
                    ),
                  const SizedBox(height: 18),
                  if (check == null) ...[
                    SahlhaPrimaryButton(
                      label: 'Check answer',
                      loading: state.checking,
                      onPressed: valid ? controller.checkCurrent : null,
                    ),
                    TextButton.icon(
                      onPressed: controller.requestSupportHint,
                      icon: const Icon(
                        Icons.lightbulb_outline_rounded,
                        size: 20,
                      ),
                      label: const Text('A little hint'),
                    ),
                  ] else
                    SahlhaPrimaryButton(
                      label: state.isLast ? 'Finish practice' : 'Next question',
                      loading: state.submitting,
                      onPressed: state.isLast
                          ? controller.submit
                          : () {
                              _answer.clear();
                              controller.next();
                              _scroll.jumpTo(0);
                            },
                    ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _feedback(BuildContext context, PracticeState state) {
    final result = state.result!;
    final text = Theme.of(context).textTheme;
    final touched = result.results.map((r) => r.skillId).toSet();
    final mastered = touched
        .where((id) => result.masteryStates[id] == 'mastered')
        .length;
    final unitReview = widget.mode == 'mastery';
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 16),
        const Center(child: LearningMark(size: 88)),
        const SizedBox(height: 24),
        Text(
          unitReview ? 'You brought it together.' : 'One more step forward.',
          textAlign: TextAlign.center,
          style: text.headlineMedium?.copyWith(height: 1.25),
        ),
        const SizedBox(height: 12),
        Text(
          mastered > 0
              ? 'Your practice is building strong understanding.'
              : 'Every try helps you see a little more.',
          textAlign: TextAlign.center,
          style: text.bodyLarge?.copyWith(color: SahlhaColors.muted),
        ),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: unitReview ? SahlhaColors.sunSoft : Colors.white,
            borderRadius: BorderRadius.circular(26),
            border: Border.all(color: SahlhaColors.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              JourneyEyebrow(
                unitReview ? 'UNIT REVIEW COMPLETE' : 'PRACTICE COMPLETE',
              ),
              const SizedBox(height: 12),
              Text(
                '${result.correct} of ${result.total} correct',
                style: text.titleLarge,
              ),
              const SizedBox(height: 14),
              SahlhaProgressBar(value: result.score),
              if (mastered > 0) ...[
                const SizedBox(height: 12),
                Text(
                  '$mastered practiced ${mastered == 1 ? 'skill is' : 'skills are'} at mastery.',
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 24),
        SahlhaPrimaryButton(
          label: 'Continue my learning path',
          onPressed: _path,
        ),
        TextButton(
          onPressed: _start,
          child: const Text('Revisit this practice'),
        ),
        const SizedBox(height: 12),
        ExpansionTile(
          title: const Text('Look back at your answers'),
          children: [
            for (var i = 0; i < result.results.length; i++)
              ListTile(
                leading: Icon(
                  result.results[i].correct
                      ? Icons.check_circle_outline_rounded
                      : Icons.lightbulb_outline_rounded,
                  color: SahlhaColors.tealDark,
                ),
                title: Text('Question ${i + 1}'),
                subtitle: Text(
                  result.results[i].correct ? 'Understood' : 'Keep practicing',
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _AnswerOption extends StatelessWidget {
  const _AnswerOption({
    required this.label,
    required this.index,
    required this.selected,
    required this.correct,
    this.onTap,
  });
  final String label;
  final int index;
  final bool selected, correct;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Semantics(
    selected: selected,
    button: true,
    enabled: onTap != null,
    child: Material(
      color: selected || correct ? SahlhaColors.tealSoft : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(
          color: selected || correct
              ? SahlhaColors.tealDark
              : SahlhaColors.line,
          width: selected ? 2 : 1,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              Container(
                width: 30,
                height: 30,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: SahlhaColors.cream,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: correct
                    ? const Icon(
                        Icons.check_rounded,
                        size: 19,
                        color: SahlhaColors.tealDark,
                      )
                    : Text('${index + 1}'),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.bodyLarge
                      ?.copyWith(height: 1.5),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
