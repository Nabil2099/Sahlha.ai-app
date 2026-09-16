import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/auth_controller.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../data/teacher_repository.dart';

/// Teacher dashboard answers: who needs support, which skill is difficult,
/// what to teach again. Readable data — no meaningless charts.
class TeacherDashboardScreen extends ConsumerWidget {
  const TeacherDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final user = ref.watch(currentUserProvider);
    final overview = ref.watch(teacherOverviewProvider);

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(teacherOverviewProvider);
            await ref.read(teacherOverviewProvider.future);
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Good day,',
                  style: text.bodyMedium?.copyWith(color: SahlhaColors.muted),
                ),
                Text(
                  user?.name.split(' ').first ?? 'Teacher',
                  style: text.headlineSmall,
                ),
                const SizedBox(height: SahlhaSpacing.lg),
                overview.when(
                  loading: () => const LoadingState(),
                  error: (e, _) => ErrorState(
                    message: e.toString(),
                    onRetry: () => ref.invalidate(teacherOverviewProvider),
                  ),
                  data: (data) => _DashboardBody(data: data),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final needing = (data['needing_support'] as List? ?? []);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _Stat(value: '${data['num_classrooms'] ?? 0}', label: 'Classes'),
            const SizedBox(width: SahlhaSpacing.sm),
            _Stat(value: '${data['num_students'] ?? 0}', label: 'Students'),
            const SizedBox(width: SahlhaSpacing.sm),
            _Stat(
              value: '${data['pending_banks'] ?? 0}',
              label: 'To review',
              highlight: (data['pending_banks'] as num? ?? 0) > 0,
            ),
          ],
        ),
        const SizedBox(height: SahlhaSpacing.xl),
        if ((data['pending_banks'] as num? ?? 0) > 0) ...[
          SahlhaCard(
            onTap: () => context.push('/teacher/classrooms'),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: const BoxDecoration(
                    color: SahlhaColors.sunSoft,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.rate_review_outlined,
                    color: Color(0xFFB45309),
                  ),
                ),
                const SizedBox(width: SahlhaSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Questions waiting for review',
                        style: text.titleMedium,
                      ),
                      Text(
                        '${data['pending_banks']} AI-generated banks need your approval.',
                        style: text.bodySmall?.copyWith(
                          color: SahlhaColors.muted,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: SahlhaColors.muted),
              ],
            ),
          ),
          const SizedBox(height: SahlhaSpacing.lg),
        ],
        Text('Students needing support', style: text.titleLarge),
        const SizedBox(height: SahlhaSpacing.sm),
        if (needing.isEmpty)
          const SahlhaCard(
            child: Text('Everyone is on track right now. Nice work.'),
          )
        else
          ...needing.take(6).map((n) {
            final item = n as Map<String, dynamic>;
            return Padding(
              padding: const EdgeInsets.only(bottom: SahlhaSpacing.sm),
              child: SahlhaCard(
                onTap: () => context.push(
                  '/teacher/students/${item['classroom_id']}/${item['student_id']}',
                ),
                padding: const EdgeInsets.all(SahlhaSpacing.md),
                child: Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: const BoxDecoration(
                        color: SahlhaColors.warningSoft,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.person_outline,
                        color: Color(0xFFB45309),
                      ),
                    ),
                    const SizedBox(width: SahlhaSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item['name']?.toString() ?? '',
                            style: text.titleMedium,
                          ),
                          Text(
                            item['classroom_name']?.toString() ?? '',
                            style: text.bodySmall?.copyWith(
                              color: SahlhaColors.muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SkillStatusBadge(state: 'needs_practice'),
                  ],
                ),
              ),
            );
          }),
        const SizedBox(height: SahlhaSpacing.xl),
        SahlhaSecondaryButton(
          label: 'View all classrooms',
          onPressed: () => context.go('/teacher/classrooms'),
        ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({
    required this.value,
    required this.label,
    this.highlight = false,
  });

  final String value;
  final String label;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Expanded(
      child: SahlhaCard(
        child: Column(
          children: [
            Text(
              value,
              style: text.headlineSmall?.copyWith(
                color: highlight ? const Color(0xFFB45309) : SahlhaColors.ink,
              ),
            ),
            Text(
              label,
              style: text.bodySmall?.copyWith(color: SahlhaColors.muted),
            ),
          ],
        ),
      ),
    );
  }
}
