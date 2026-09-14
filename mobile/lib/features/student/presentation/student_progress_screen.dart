import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../data/student_repository.dart';

/// Student progress: mastery first (you vs your past self), grades secondary.
/// No leaderboards, no peer comparison — ever.
class StudentProgressScreen extends ConsumerWidget {
  const StudentProgressScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final progress = ref.watch(studentProgressProvider());
    return Scaffold(
      appBar: const SahlhaAppBar(title: 'My Progress'),
      body: progress.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(
            message: e.toString(),
            onRetry: () => ref.invalidate(studentProgressProvider())),
        data: (data) {
          final rooms = (data['classrooms'] as List? ?? []);
          if (rooms.isEmpty) {
            return EmptyState(
              title: 'Nothing here yet',
              message: 'Join a classroom to start tracking your progress.',
              action: SahlhaPrimaryButton(
                label: 'Join a classroom',
                onPressed: () => context.push('/student/join'),
              ),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            itemCount: rooms.length,
            separatorBuilder: (_, __) =>
                const SizedBox(height: SahlhaSpacing.lg),
            itemBuilder: (_, i) =>
                _ClassroomProgress(room: rooms[i] as Map<String, dynamic>),
          );
        },
      ),
    );
  }
}

class _ClassroomProgress extends StatelessWidget {
  const _ClassroomProgress({required this.room});

  final Map<String, dynamic> room;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final summary =
        (room['summary'] as Map?)?.cast<String, dynamic>() ?? {};
    int count(String k) => (summary[k] as num?)?.toInt() ?? 0;
    final total =
        count('mastered') + count('developing') + count('needs_practice') + count('not_started');
    final grades = (room['grades'] as List? ?? []);
    final units = (room['units'] as List? ?? []);

    return SahlhaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(room['subject']?.toString() ?? '', style: text.titleLarge),
          Text(room['name']?.toString() ?? '',
              style: text.bodySmall?.copyWith(color: SahlhaColors.muted)),
          const SizedBox(height: SahlhaSpacing.md),
          Row(
            children: [
              MasteryRing(mastered: count('mastered'), total: total),
              const SizedBox(width: SahlhaSpacing.lg),
              Expanded(
                child: Column(
                  children: [
                    _MasteryRow(label: 'Mastered', value: count('mastered'), state: 'mastered'),
                    _MasteryRow(
                        label: 'Developing', value: count('developing'), state: 'developing'),
                    _MasteryRow(
                        label: 'Needs practice',
                        value: count('needs_practice'),
                        state: 'needs_practice'),
                    _MasteryRow(
                        label: 'Not started',
                        value: count('not_started'),
                        state: 'not_started'),
                  ],
                ),
              ),
            ],
          ),
          if (grades.isNotEmpty) ...[
            const SizedBox(height: SahlhaSpacing.md),
            Text('Recent practice',
                style: text.titleMedium),
            const SizedBox(height: SahlhaSpacing.sm),
            ...(grades.take(3)).map((g) {
              final grade = g as Map<String, dynamic>;
              final pct =
                  (((grade['score'] as num?)?.toDouble() ?? 0) * 100).round();
              return Padding(
                padding:
                    const EdgeInsets.only(bottom: SahlhaSpacing.xs),
                child: Row(
                  children: [
                    Expanded(
                        child:
                            SahlhaProgressBar(value: pct / 100, height: 8)),
                    const SizedBox(width: SahlhaSpacing.sm),
                    Text('$pct%', style: text.bodySmall),
                  ],
                ),
              );
            }),
          ],
          if (units.isNotEmpty) ...[
            const SizedBox(height: SahlhaSpacing.md),
            SahlhaSecondaryButton(
              label: 'Continue learning',
              onPressed: () => context.go(
                  '/student/learn?classroomId=${room['classroom_id']}'),
            ),
          ],
        ],
      ),
    );
  }
}

class _MasteryRow extends StatelessWidget {
  const _MasteryRow(
      {required this.label, required this.value, required this.state});

  final String label;
  final int value;
  final String state;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
                color: SahlhaColors.mastery(state),
                shape: BoxShape.circle),
          ),
          const SizedBox(width: SahlhaSpacing.sm),
          Expanded(child: Text(label, style: text.bodyMedium)),
          Text('$value',
              style: text.bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}
