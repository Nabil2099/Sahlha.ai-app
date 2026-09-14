import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/auth_controller.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../learning_profile/data/learning_profile_repository.dart';
import '../data/student_repository.dart';

/// Student Home answers ONE question: "What should I do next?"
class StudentHomeScreen extends ConsumerWidget {
  const StudentHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final user = ref.watch(currentUserProvider);
    final home = ref.watch(studentHomeProvider);
    final profile = ref.watch(learningProfileProvider);

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(studentHomeProvider);
            await ref.read(studentHomeProvider.future);
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Good day,',
                              style: text.bodyMedium?.copyWith(
                                  color: SahlhaColors.muted)),
                          Text(user?.name.isNotEmpty == true
                                  ? '${user!.name.split(' ').first}!'
                                  : 'Learner!',
                              style: text.headlineSmall),
                        ],
                      ),
                    ),
                    const SahlhaLogo(size: 36, showWordmark: false),
                  ],
                ),
                const SizedBox(height: SahlhaSpacing.lg),
                // Gentle nudge to finish the learning profile.
                profile.whenOrNull(
                      data: (p) => !p.onboardingCompleted
                          ? SahlhaCard(
                              onTap: () => context.push('/student/setup'),
                              child: Row(
                                children: [
                                  const Icon(Icons.tune,
                                      color: SahlhaColors.teal),
                                  const SizedBox(width: SahlhaSpacing.md),
                                  Expanded(
                                    child: Text(
                                      'Tell Sahlha how you learn best (1 minute).',
                                      style: text.titleMedium,
                                    ),
                                  ),
                                  const Icon(Icons.chevron_right,
                                      color: SahlhaColors.muted),
                                ],
                              ),
                            )
                          : null,
                    ) ??
                    const SizedBox.shrink(),
                if (profile.valueOrNull?.onboardingCompleted == false)
                  const SizedBox(height: SahlhaSpacing.md),
                home.when(
                  loading: () => const LoadingState(
                      message: 'Getting your next step…'),
                  error: (e, _) => ErrorState(
                      message: e.toString(),
                      onRetry: () => ref.invalidate(studentHomeProvider)),
                  data: (data) => _HomeBody(data: data),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

List<Widget> _supplementaryCard(
    BuildContext context, Map<String, dynamic> data) {
  final supp = data['supplementary'] as Map<String, dynamic>?;
  final total = (supp?['total_skills'] as num?)?.toInt() ?? 0;
  if (supp == null || total == 0) return [];
  final text = Theme.of(context).textTheme;
  return [
    const SizedBox(height: SahlhaSpacing.xl),
    Text('Extra practice', style: text.titleLarge),
    const SizedBox(height: SahlhaSpacing.sm),
    SahlhaCard(
      onTap: () => context.push('/student/learn?supplementary=true'),
      child: Row(
        children: [
          Expanded(
            child: Text('$total extra skills from your family',
                style: text.titleMedium),
          ),
          const Icon(Icons.chevron_right, color: SahlhaColors.muted),
        ],
      ),
    ),
  ];
}

class _HomeBody extends StatelessWidget {
  const _HomeBody({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final rooms = (data['classrooms'] as List? ?? []);
    if (rooms.isEmpty) {
      return EmptyState(
        title: 'No classroom yet',
        message:
            'Ask your teacher for the classroom code, then join to start learning.',
        action: SahlhaPrimaryButton(
          label: 'Join a classroom',
          onPressed: () => context.push('/student/join'),
        ),
      );
    }
    final first = rooms.first as Map<String, dynamic>;
    final current = first['current'] as Map<String, dynamic>?;
    final summary =
        (first['summary'] as Map?)?.cast<String, dynamic>() ?? {};
    final mastered = (summary['mastered'] as num?)?.toInt() ?? 0;
    final total = (first['total_skills'] as num?)?.toInt() ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (current != null) ...[
          Text('Continue learning', style: text.titleLarge),
          const SizedBox(height: SahlhaSpacing.sm),
          SahlhaCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(first['subject']?.toString() ?? '',
                    style: text.bodySmall
                        ?.copyWith(color: SahlhaColors.tealDark)),
                const SizedBox(height: 2),
                Text(current['name']?.toString() ?? 'Your next skill',
                    style: text.titleLarge),
                const SizedBox(height: SahlhaSpacing.md),
                SahlhaPrimaryButton(
                  label: 'Continue',
                  onPressed: () => context.push(
                    '/student/skill/${current['skill_id']}?materialId=${current['material_id']}&classroomId=${first['classroom_id']}',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: SahlhaSpacing.xl),
        ],
        Text("Today's goal", style: text.titleLarge),
        const SizedBox(height: SahlhaSpacing.sm),
        SahlhaCard(
          child: Row(
            children: [
              MasteryRing(mastered: mastered, total: total, size: 84),
              const SizedBox(width: SahlhaSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      total == 0
                          ? 'Your learning path is being prepared.'
                          : '$mastered of $total skills mastered',
                      style: text.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Complete 1 lesson to keep going.',
                      style: text.bodySmall
                          ?.copyWith(color: SahlhaColors.muted),
                    ),
                    const SizedBox(height: SahlhaSpacing.sm),
                    SahlhaSecondaryButton(
                      label: 'My learning path',
                      onPressed: () => context.go(
                          '/student/learn?classroomId=${first['classroom_id']}'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        ..._supplementaryCard(context, data),
        if (rooms.length > 1) ...[
          const SizedBox(height: SahlhaSpacing.xl),
          Text('My classrooms', style: text.titleLarge),
          const SizedBox(height: SahlhaSpacing.sm),
          ...rooms.skip(1).map((r) {
            final room = r as Map<String, dynamic>;
            return Padding(
              padding: const EdgeInsets.only(bottom: SahlhaSpacing.sm),
              child: SahlhaCard(
                onTap: () => context.go(
                    '/student/learn?classroomId=${room['classroom_id']}'),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(room['name']?.toString() ?? '',
                              style: text.titleMedium),
                          Text(room['subject']?.toString() ?? '',
                              style: text.bodySmall?.copyWith(
                                  color: SahlhaColors.muted)),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right,
                        color: SahlhaColors.muted),
                  ],
                ),
              ),
            );
          }),
        ],
      ],
    );
  }
}
