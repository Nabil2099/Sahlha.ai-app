import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/auth_controller.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/widgets/sahlha_widgets.dart'
    show EmptyState, ErrorState, SahlhaPrimaryButton;
import '../data/student_repository.dart';
import 'journey_presentation.dart';
import 'widgets/engagement.dart';
import 'widgets/learning_journey.dart';

class StudentHomeScreen extends ConsumerWidget {
  const StudentHomeScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final home = ref.watch(studentHomeProvider);
    final name = cleanStudentText(user?.name ?? '').split(' ').first;
    final returning = (home.asData?.value['classrooms'] as List? ?? [])
        .whereType<Map>()
        .any((r) => r['recent_practiced_at'] != null);
    return Scaffold(
      body: SafeArea(
        child: StudentCanvas(
          child: RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(studentHomeProvider);
              ref.invalidate(studentLearningPathProvider);
              await ref.read(studentHomeProvider.future);
            },
            child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 30),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Sahlha',
                            style: Theme.of(context).textTheme.headlineMedium
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Icon(Icons.lock_outline_rounded, size: 20),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  'Learning made for you',
                  style: Theme.of(context).textTheme.bodyLarge
                      ?.copyWith(color: SahlhaColors.muted),
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          returning
                              ? (name.isEmpty
                                    ? 'Welcome back! Ready for your next step?'
                                    : 'Welcome back, $name!')
                              : "Let\u2019s do one learning step today!",
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    const SahlhaCompanion(size: 76),
                  ],
                ),
                const SizedBox(height: 22),
                home.when(
                  loading: () =>
                      const SizedBox(height: 320, child: JourneyLoading()),
                  error: (_, _) => ErrorState(
                    message: "We couldn't load your next step.",
                    onRetry: () => ref.invalidate(studentHomeProvider),
                  ),
                  data: (data) => _HomeLearning(data: data),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HomeLearning extends ConsumerWidget {
  const _HomeLearning({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rooms = (data['classrooms'] as List? ?? []).whereType<Map>().toList();
    final supp = data['supplementary'] as Map?;
    final hasExtra = (supp?['total_skills'] as num? ?? 0) > 0;
    final room =
        rooms.where((r) => r['current'] != null).firstOrNull ??
        rooms.firstOrNull;
    final useExtra =
        hasExtra &&
        (room == null || room['current'] == null) &&
        supp?['current'] != null;
    if (room == null && !hasExtra) {
      return EmptyState(
        title: 'Your first step is waiting',
        message: 'Ask your teacher for a classroom code to begin.',
        action: SahlhaPrimaryButton(
          label: 'Join a classroom',
          onPressed: () => context.push('/student/join'),
        ),
      );
    }
    final roomId = useExtra ? null : room?['classroom_id']?.toString();
    final extra = useExtra || room == null;
    // Real submitted-practice recency across classrooms: powers the
    // comeback line and the daily goal. No extra request — it rides on
    // the home payload's `recent_practiced_at` fields.
    final recent = mostRecentStamp(
      rooms.map((r) => r['recent_practiced_at']?.toString()),
    );
    final comeback = relativeDayLabel(recent);
    final provider = studentLearningPathProvider(
      classroomId: roomId,
      supplementary: extra,
    );
    final path = ref.watch(provider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (comeback.isNotEmpty) ...[
          Row(
            children: [
              const Icon(
                Icons.history_rounded,
                size: 18,
                color: SahlhaColors.muted,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Welcome back — you practiced ${comeback.toLowerCase()}.',
                  style: Theme.of(context).textTheme.bodyMedium
                      ?.copyWith(color: SahlhaColors.muted),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
        ],
        path.when(
          loading: () => const SizedBox(height: 260, child: JourneyLoading()),
          error: (_, _) => ErrorState(
            message: "We couldn't load your next lesson.",
            onRetry: () => ref.invalidate(provider),
          ),
          data: (value) {
            final journey = LearningJourney.fromJson(
              value,
              subject: room?['subject']?.toString() ?? '',
            );
            final unit = journey.activeUnit;
            final current = unit?.current;
            if (unit == null || journey.total == 0) {
              return const EmptyState(
                title: 'Your learning path is being prepared.',
                message: 'Come back soon for your first step.',
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (current != null)
                  CurrentSkillCard(
                    title: current.title,
                    contextLabel: comeback.isNotEmpty
                        ? 'Continue where you left off'
                        : 'Continue learning',
                    questions: current.skill.practiceQuestions,
                    minutes:
                        ((current.skill.description
                                        .split(RegExp(r'\s+'))
                                        .length /
                                    150) +
                                current.skill.practiceQuestions * .6)
                            .ceil()
                            .clamp(1, 60),
                    subtitle: journey.units.isEmpty ? '' : unit.title,
                    started: current.skill.attempted > 0,
                    progress: unit.steps.isEmpty
                        ? null
                        : (current.index + 1) / unit.steps.length,
                    effort: effortLabelForMastery(current.skill.state),
                    onTap: () => context.push(
                      lessonLocation(
                        current,
                        classroomId: roomId,
                        supplementary: extra,
                      ),
                    ),
                    onContinue: () => context.push(
                      lessonLocation(
                        current,
                        classroomId: roomId,
                        supplementary: extra,
                      ),
                    ),
                  )
                else
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: SahlhaColors.tealSoft,
                      borderRadius: BorderRadius.circular(28),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SahlhaCompanion(size: 56),
                        const SizedBox(height: 14),
                        Text(
                          journey.mastered == journey.total
                              ? 'Look how far you’ve come.'
                              : 'Learn at your own pace.',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: () => context.go(
                            learningLocation(
                              classroomId: roomId,
                              supplementary: extra,
                            ),
                          ),
                          child: const Text('Explore your path'),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 24),
                Builder(
                  builder: (_) {
                    final goal = dailyGoalFor(
                      hasStep: journey.total > 0,
                      recentPracticedAt: recent,
                      stepTitle: current?.title,
                    );
                    return DailyGoalCard(goal: goal);
                  },
                ),
                const SizedBox(height: 22),
                Text(
                  'Recent activity',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                for (final step
                    in journey.units
                        .expand((u) => u.steps)
                        .where((s) => s.skill.attempted > 0)
                        .take(1))
                  Card(
                    elevation: 0,
                    color: Colors.white,
                    child: ListTile(
                      leading: const Icon(
                        Icons.auto_stories_outlined,
                        color: SahlhaColors.tealDark,
                      ),
                      title: Text(step.title),
                      subtitle: Text(effortLabelForMastery(step.skill.state)),
                      trailing: step.skill.state == 'mastered'
                          ? const Icon(Icons.check, color: SahlhaColors.success)
                          : null,
                    ),
                  ),
                if (!journey.units
                    .expand((u) => u.steps)
                    .any((s) => s.skill.attempted > 0))
                  const Text(
                    'Your learning steps will appear here after practice.',
                  ),
                TextButton(
                  onPressed: () => context.go(
                    learningLocation(classroomId: roomId, supplementary: extra),
                  ),
                  child: const Text('See your learning path'),
                ),
              ],
            );
          },
        ),
        if (rooms.length > 1) ...[
          const SizedBox(height: 16),
          const JourneyEyebrow('MORE TO EXPLORE'),
          for (final other in rooms.where((r) => r['classroom_id'] != roomId))
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                studentTitle(
                  other['subject']?.toString() ?? '',
                  fallback: 'Your classroom',
                ),
              ),
              trailing: const Icon(Icons.arrow_forward_rounded),
              onTap: () => context.go(
                learningLocation(
                  classroomId: other['classroom_id']?.toString(),
                ),
              ),
            ),
        ],
        if (hasExtra && !extra)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(
              Icons.auto_stories_outlined,
              color: SahlhaColors.tealDark,
            ),
            title: const Text('Extra learning'),
            subtitle: const Text('A little support from your family'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.go(learningLocation(supplementary: true)),
          ),
        if (data['onboarding_completed'] != true)
          TextButton.icon(
            onPressed: () => context.push('/student/setup'),
            icon: const Icon(Icons.tune_rounded),
            label: const Text('Make learning feel right for you'),
          ),
      ],
    );
  }
}
