import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/widgets/sahlha_widgets.dart'
    show SahlhaAppBar, ErrorState, EmptyState, SahlhaPrimaryButton;
import '../data/student_repository.dart';
import 'journey_presentation.dart';
import 'widgets/learning_journey.dart';

class StudentProgressScreen extends ConsumerWidget {
  const StudentProgressScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = studentProgressProvider();
    final response = ref.watch(provider);
    return Scaffold(
      appBar: const SahlhaAppBar(title: 'See how you’re growing'),
      body: StudentCanvas(
        child: response.when(
          loading: () => const JourneyLoading(),
          error: (_, _) => ErrorState(
            message: "We couldn't load your progress.",
            onRetry: () => ref.invalidate(provider),
          ),
          data: (data) {
            final rooms = (data['classrooms'] as List? ?? [])
                .whereType<Map>()
                .toList();
            if (rooms.isEmpty) {
              return EmptyState(
                title: 'Every journey starts with a step',
                message: 'Join your classroom. Your progress will grow here as you practice.',
                action: SahlhaPrimaryButton(
                  label: 'Join a classroom',
                  onPressed: () => context.push('/student/join'),
                ),
              );
            }
            return RefreshIndicator(
              onRefresh: () async {
                ref.invalidate(provider);
                await ref.read(provider.future);
              },
              child: ListView(
                padding: const EdgeInsets.all(24),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  const JourneyEyebrow('YOUR PROGRESS, AT YOUR PACE'),
                  const SizedBox(height: 10),
                  Text(
                    'Understanding takes practice.',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Look at what you’re learning. There’s no race to finish.',
                  ),
                  const SizedBox(height: 24),
                  for (final room in rooms) _ProgressRoom(room: room),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _ProgressRoom extends StatelessWidget {
  const _ProgressRoom({required this.room});
  final Map room;
  @override
  Widget build(BuildContext context) {
    final journey = LearningJourney.fromJson({
      'units': room['units'] ?? [],
    }, subject: room['subject']?.toString() ?? '');
    final summary = room['summary'] as Map? ?? {};
    final mastered = (summary['mastered'] as num?)?.toInt() ?? journey.mastered;
    final total = journey.total;
    final text = Theme.of(context).textTheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: SahlhaColors.line),
      ),
      child: Material(
        color: Colors.transparent,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              studentTitle(
                room['subject']?.toString() ?? '',
                fallback: 'Your learning',
              ),
              style: text.titleLarge,
            ),
            const SizedBox(height: 8),
            Text('$mastered of $total skills mastered'),
            const SizedBox(height: 14),
            UnitProgressBar(completed: mastered, total: total),
            const SizedBox(height: 12),
            for (final unit in journey.units)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Text(unit.title),
                subtitle: Text(
                  'Unit ${unit.number} · ${unit.mastered} of ${unit.steps.length} mastered',
                ),
                children: [
                  for (final step in unit.steps)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        step.skill.state == 'mastered'
                            ? Icons.check_circle_rounded
                            : Icons.menu_book_outlined,
                        color: SahlhaColors.tealDark,
                      ),
                      title: Text(step.title),
                      subtitle: Text(switch (step.skill.state) {
                        'mastered' => 'Mastered',
                        'developing' => 'Growing in confidence',
                        'needs_practice' => 'A little more practice',
                        _ => 'Waiting to be explored',
                      }),
                    ),
                ],
              ),
            TextButton.icon(
              onPressed: () => context.go(
                learningLocation(classroomId: room['classroom_id']?.toString()),
              ),
              icon: const Icon(Icons.route_outlined),
              label: const Text('Visit this learning path'),
            ),
            if ((room['grades'] as List? ?? []).isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Recent practice'),
                children: [
                  for (final grade
                      in (room['grades'] as List).whereType<Map>().take(3))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Practice session'),
                      trailing: Text(
                        '${(((grade['score'] as num? ?? 0) * 100).round())}%',
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
