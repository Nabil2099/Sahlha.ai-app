import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/sahlha_colors.dart';
import '../../../../core/widgets/sahlha_widgets.dart';
import '../../data/student_repository.dart';
import '../journey_presentation.dart';
import '../practice_controller.dart';
import 'sahlha_companion.dart';

class SkillCompletion extends ConsumerWidget {
  const SkillCompletion({
    super.key,
    required this.state,
    required this.elapsed,
    required this.onPath,
    required this.onRetry,
  });
  final PracticeState state;
  final Duration elapsed;
  final VoidCallback onPath, onRetry;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = state.result!;
    final path = ref.watch(
      studentLearningPathProvider(
        classroomId: state.classroomId,
        supplementary: state.childScope,
      ),
    );
    final journey = path.asData == null
        ? null
        : LearningJourney.fromJson(path.asData!.value);
    final steps =
        journey?.units.expand((u) => u.steps).toList() ?? <JourneyStep>[];
    final touched = result.results.map((r) => r.skillId).toSet();
    final practiced = steps
        .where(
          (s) =>
              s.materialId == state.materialId &&
              touched.contains(s.skill.skillId),
        )
        .toList();
    final next = journey?.activeUnit?.current;
    final titles = practiced.map((s) => s.title).join(', ');
    final handled = practiced.where(
      (s) =>
          result.results.any((r) => r.skillId == s.skill.skillId && r.correct),
    );
    final review = practiced.where(
      (s) => result.masteryStates[s.skill.skillId] != 'mastered',
    );
    final mastered = touched.any(
      (id) => result.masteryStates[id] == 'mastered',
    );
    final text = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
      children: [
        Center(
          child: SahlhaCompanion(
            size: 120,
            mood: mastered ? CompanionMood.celebrating : CompanionMood.retry,
          ),
        ),
        const SizedBox(height: 18),
        Text(
          'Nice work!',
          textAlign: TextAlign.center,
          style: text.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        Text(
          titles.isEmpty
              ? 'You completed your practice'
              : touched.every((id) => result.masteryStates[id] == 'mastered')
              ? 'You completed\n$titles'
              : 'You practiced\n$titles',
          textAlign: TextAlign.center,
          style: text.titleMedium,
        ),
        const SizedBox(height: 26),
        Container(
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 6),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _Stat(Icons.assignment_outlined, '${result.total}', 'Questions'),
              _Stat(
                Icons.check_circle,
                '${result.correct}/${result.total}',
                'Correct',
              ),
              _Stat(
                Icons.timer_outlined,
                '${elapsed.inMinutes}:${(elapsed.inSeconds % 60).toString().padLeft(2, '0')}',
                'Time',
              ),
            ],
          ),
        ),
        const SizedBox(height: 22),
        _Recap(
          icon: Icons.lightbulb_outline,
          title: 'You learned',
          body: practiced.isEmpty
              ? 'You worked through ${result.total} ${result.total == 1 ? "question" : "questions"}.'
              : practiced
                    .map(
                      (s) => cleanStudentText(s.skill.description).isEmpty
                          ? s.title
                          : cleanStudentText(s.skill.description),
                    )
                    .join('\n'),
          color: const Color(0xFFFFEABB),
        ),
        _Recap(
          icon: Icons.star_outline_rounded,
          title: 'You handled well',
          body: handled.isEmpty
              ? 'You gave yourself time to practice.'
              : handled.map((s) => s.title).join(', '),
          color: const Color(0xFFFFEABB),
        ),
        _Recap(
          icon: Icons.refresh,
          title: 'Practice again later',
          body: review.isEmpty
              ? 'Revisit these ideas whenever you need a reminder.'
              : review.map((s) => s.title).join(', '),
          color: const Color(0xFFCFEFF4),
        ),
        const SizedBox(height: 16),
        SahlhaPrimaryButton(
          label: next == null
              ? 'Continue my learning path'
              : touched.contains(next.skill.skillId)
              ? 'Continue learning'
              : 'Continue to next skill',
          onPressed: next == null
              ? onPath
              : () => context.go(
                  lessonLocation(
                    next,
                    classroomId: state.classroomId,
                    supplementary: state.childScope,
                  ),
                ),
        ),
        TextButton(
          onPressed: onRetry,
          child: const Text('Revisit this practice'),
        ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.icon, this.value, this.label);
  final IconData icon;
  final String value, label;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Column(
      children: [
        Icon(icon, color: SahlhaColors.success, size: 21),
        const SizedBox(height: 5),
        Text(value, style: Theme.of(context).textTheme.titleMedium),
        Text(
          label,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    ),
  );
}

class _Recap extends StatelessWidget {
  const _Recap({
    required this.icon,
    required this.title,
    required this.body,
    required this.color,
  });
  final IconData icon;
  final String title, body;
  final Color color;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CircleAvatar(
          radius: 21,
          backgroundColor: color,
          child: Icon(icon, color: SahlhaColors.tealDark),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 5),
              Text(body, style: Theme.of(context).textTheme.bodyMedium),
            ],
          ),
        ),
      ],
    ),
  );
}
