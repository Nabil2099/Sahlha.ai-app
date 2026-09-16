import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/student_repository.dart';
import '../journey_presentation.dart';
import '../../../../core/widgets/sahlha_widgets.dart';

class QuickCheckIntro extends ConsumerWidget {
  const QuickCheckIntro({
    super.key,
    this.classroomId,
    this.materialId,
    this.supplementary = false,
    required this.onStart,
  });
  final String? classroomId, materialId;
  final bool supplementary;
  final VoidCallback onStart;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = studentLearningPathProvider(
      classroomId: classroomId,
      supplementary: supplementary,
    );
    return ref
        .watch(provider)
        .when(
          loading: () =>
              const LoadingState(message: 'Opening your Quick Check...'),
          error: (_, _) => ErrorState(
            message: 'Your Quick Check could not open.',
            onRetry: () => ref.invalidate(provider),
          ),
          data: (data) {
            final journey = LearningJourney.fromJson(data);
            final learned = journey.units
                .where((u) => u.source.materialId == materialId)
                .expand((u) => u.steps)
                .where((s) => s.learned)
                .toList();
            final ready =
                learned.length >= 2 &&
                learned.every((s) => s.skill.exerciseReady);
            final questions = learned.fold(
              0,
              (sum, s) => sum + s.skill.practiceQuestions,
            );
            return ListView(
              padding: const EdgeInsets.all(28),
              children: [
                const SizedBox(height: 50),
                const Icon(
                  Icons.flag_outlined,
                  size: 76,
                  color: Color(0xFF8060DC),
                ),
                const SizedBox(height: 22),
                Text(
                  'Quick Check',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 14),
                const Text(
                  "Test what you've learned\nso far in this unit.",
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 28),
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF0EBFF),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Column(
                    children: [
                      if (questions > 0)
                        ListTile(
                          leading: const Icon(Icons.quiz_outlined),
                          title: Text('~$questions questions'),
                        ),
                      ListTile(
                        leading: const Icon(Icons.layers_outlined),
                        title: Text('${learned.length} practiced skills'),
                      ),
                      const ListTile(
                        leading: Icon(Icons.route_outlined),
                        title: Text('Build understanding for your next steps'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF8060DC),
                    minimumSize: const Size(48, 54),
                  ),
                  onPressed: ready ? onStart : null,
                  icon: const Icon(Icons.arrow_forward),
                  label: const Text('Start Quick Check'),
                ),
                if (!ready)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text(
                      'Practice at least two skills with ready questions first.',
                      textAlign: TextAlign.center,
                    ),
                  ),
              ],
            );
          },
        );
  }
}
