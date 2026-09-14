import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/api/api_exception.dart';
import '../data/student_repository.dart';
import '../domain/assessment_models.dart';

part 'practice_controller.freezed.dart';
part 'practice_controller.g.dart';

@freezed
class PracticeState with _$PracticeState {
  const factory PracticeState({
    @Default(false) bool starting,
    String? assessmentId,
    @Default([]) List<PracticeQuestion> questions,
    @Default(0) int index,
    @Default({}) Map<String, Object?> answers,
    @Default(false) bool submitting,
    AssessmentResult? result,
    String? error,
    @Default({}) Map<String, CheckResult> checked,
    // Progressive support level for the current question (hint -> example).
    @Default(0) int supportLevel,
  }) = _PracticeState;
}

extension PracticeStateX on PracticeState {
  PracticeQuestion? get current =>
      questions.isEmpty || index >= questions.length ? null : questions[index];
  bool get isLast => questions.isNotEmpty && index >= questions.length - 1;
  int get answered => answers.length;
}

@riverpod
class PracticeController extends _$PracticeController {
  @override
  PracticeState build() => const PracticeState();

  Future<void> start({
    String? classroomId,
    String? materialId,
    String? skillId,
    bool childScope = false,
  }) async {
    state = state.copyWith(starting: true, error: null, result: null);
    try {
      final started =
          await ref.read(studentRepositoryProvider).startAssessment(
                classroomId: classroomId,
                materialId: materialId,
                skillId: skillId,
                childScope: childScope,
              );
      state = PracticeState(
          assessmentId: started.assessmentId, questions: started.questions);
    } on ApiException catch (e) {
      state = state.copyWith(starting: false, error: e.message);
    }
  }

  void answerCurrent(Object? answer) {
    final q = state.current;
    if (q == null || state.result != null) return;
    state = state.copyWith(
        answers: {...state.answers, q.id: answer}, supportLevel: 0);
  }

  Future<void> checkCurrent() async {
    final q = state.current;
    final id = state.assessmentId;
    if (q == null || id == null || state.checked.containsKey(q.id)) return;
    final answer = state.answers[q.id];
    state = state.copyWith(error: null);
    try {
      final res = await ref.read(studentRepositoryProvider).checkAnswer(
            assessmentId: id,
            questionId: q.id,
            answer: answer,
          );
      state = state.copyWith(checked: {...state.checked, q.id: res});
    } on ApiException catch (e) {
      state = state.copyWith(error: e.message);
    }
  }

  void next() {
    if (!state.isLast) {
      state = state.copyWith(index: state.index + 1, supportLevel: 0);
    }
  }

  void previous() {
    if (state.index > 0) {
      state = state.copyWith(index: state.index - 1, supportLevel: 0);
    }
  }

  /// Progressive support without giving away the answer.
  void requestSupportHint() {
    state = state.copyWith(supportLevel: state.supportLevel + 1);
    ref.read(studentRepositoryProvider).supportSignal('hint_used');
  }

  Future<void> submit() async {
    final id = state.assessmentId;
    if (id == null || state.submitting) return;
    state = state.copyWith(submitting: true, error: null);
    try {
      final result =
          await ref.read(studentRepositoryProvider).submitAssessment(
                assessmentId: id,
                answers: state.answers,
              );
      state = state.copyWith(submitting: false, result: result);
      // Refresh progress-dependent providers.
      ref.invalidate(studentHomeProvider);
      ref.invalidate(studentProgressProvider);
    } on ApiException catch (e) {
      state = state.copyWith(submitting: false, error: e.message);
    }
  }

  void reset() => state = const PracticeState();
}
