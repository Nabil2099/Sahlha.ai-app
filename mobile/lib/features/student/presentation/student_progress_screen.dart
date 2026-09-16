import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/widgets/sahlha_widgets.dart'
    show SahlhaAppBar, ErrorState, EmptyState, SahlhaPrimaryButton;
import '../data/student_repository.dart';
import 'journey_presentation.dart';
import 'widgets/engagement.dart';
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
                children: [for (final room in rooms) _ProgressRoom(room: room)],
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
    final steps = journey.units.expand((u) => u.steps).toList();
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          studentTitle(
            room['subject']?.toString() ?? '',
            fallback: 'Your learning',
          ),
          style: text.titleMedium,
        ),
        const SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final status in [
              (
                'mastered',
                'Mastered',
                const Color(0xFFDEFBE5),
                const Color(0xFF138A43),
              ),
              (
                'developing',
                'Developing',
                const Color(0xFFFFF3D5),
                const Color(0xFF9C6900),
              ),
              (
                'needs_practice',
                'Needs Practice',
                const Color(0xFFFFE8EC),
                const Color(0xFFB63752),
              ),
            ])
              Expanded(
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  padding: const EdgeInsets.symmetric(
                    vertical: 16,
                    horizontal: 5,
                  ),
                  decoration: BoxDecoration(
                    color: status.$3,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    children: [
                      Text(
                        '${steps.where((s) => s.skill.state == status.$1).length}',
                        style: text.headlineMedium?.copyWith(color: status.$4),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        status.$2,
                        textAlign: TextAlign.center,
                        style: text.labelSmall,
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 26),
        Text('Practiced skills', style: text.titleMedium),
        const SizedBox(height: 10),
        for (final step in steps.where((s) => s.skill.attempted > 0).take(5))
          Card(
            elevation: 0,
            color: Colors.white,
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: SahlhaColors.masterySoft(step.skill.state),
                child: Icon(
                  step.skill.state == 'mastered'
                      ? Icons.arrow_upward_rounded
                      : Icons.auto_stories_outlined,
                  color: SahlhaColors.mastery(step.skill.state),
                ),
              ),
              title: Text(step.title),
              subtitle: Text(switch (step.skill.state) {
                'mastered' => 'Mastered',
                'developing' => 'Keep building your understanding',
                _ => 'Keep going',
              }),
              onTap: () => context.push(
                lessonLocation(
                  step,
                  classroomId: room['classroom_id']?.toString(),
                ),
              ),
            ),
          ),
        if (!steps.any((s) => s.skill.attempted > 0))
          const Text('Your progress will appear after your first practice.'),
        if ((room['grades'] as List? ?? []).isNotEmpty) ...[
          const SizedBox(height: 18),
          Text('Recently practiced', style: text.titleMedium),
          for (final grade in (room['grades'] as List).whereType<Map>().take(3))
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.history, color: SahlhaColors.tealDark),
              title: const Text('Practice session'),
              subtitle: Text(relativeDayLabel(grade['created_at']?.toString())),
              trailing: Text(
                '${((grade['score'] as num? ?? 0) * 100).round()}%',
              ),
            ),
        ],
        TextButton.icon(
          onPressed: () => context.go(
            learningLocation(classroomId: room['classroom_id']?.toString()),
          ),
          icon: const Icon(Icons.route_outlined),
          label: const Text('Visit this learning path'),
        ),
        const SizedBox(height: 24),
      ],
    );
  }
}
