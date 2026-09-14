import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../data/teacher_repository.dart';

/// Teacher view of one student's progress. Support language only —
/// "needs additional support", never deficit/medical language.
class StudentDetailScreen extends ConsumerWidget {
  const StudentDetailScreen(
      {super.key, required this.classroomId, required this.studentId});

  final String classroomId;
  final String studentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final detail = ref.watch(
        _studentDetailProvider((classroomId, studentId)));
    return Scaffold(
      appBar: const SahlhaAppBar(title: 'Student Progress'),
      body: detail.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(
            message: e.toString(),
            onRetry: () => ref.invalidate(
                _studentDetailProvider((classroomId, studentId)))),
        data: (data) {
          final units = (data['units'] as List? ?? []);
          final grades = (data['grades'] as List? ?? []);
          final support =
              (data['support_summary'] as List? ?? []).cast<String>();
          final states = [
            for (final u in units)
              for (final s in ((u as Map)['skills'] as List? ?? []))
                (s as Map)['state']?.toString() ?? 'not_started'
          ];
          int count(String k) => states.where((s) => s == k).length;
          return ListView(
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            children: [
              SahlhaCard(
                child: Row(
                  children: [
                    MasteryRing(
                        mastered: count('mastered'),
                        total: states.length),
                    const SizedBox(width: SahlhaSpacing.lg),
                    Expanded(
                      child: Column(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          Text('Overall mastery',
                              style: text.titleMedium),
                          const SizedBox(height: 4),
                          Text(
                            '${count('mastered')} mastered · ${count('developing')} developing · ${count('needs_practice')} need practice',
                            style: text.bodySmall?.copyWith(
                                color: SahlhaColors.muted),
                          ),
                          if (grades.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              'Recent practice: ${((((grades.first as Map)['score'] as num?)?.toDouble() ?? 0) * 100).round()}%',
                              style: text.bodySmall,
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              if (support.isNotEmpty) ...[
                const SizedBox(height: SahlhaSpacing.md),
                SahlhaCard(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Text('What seems to help',
                          style: text.titleMedium),
                      const SizedBox(height: SahlhaSpacing.sm),
                      ...support.map((s) => Padding(
                            padding: const EdgeInsets.only(
                                bottom: SahlhaSpacing.xs),
                            child: Row(
                              crossAxisAlignment:
                                  CrossAxisAlignment.start,
                              children: [
                                const Icon(Icons.check,
                                    size: 18,
                                    color: SahlhaColors.teal),
                                const SizedBox(
                                    width: SahlhaSpacing.sm),
                                Expanded(
                                    child: Text(s,
                                        style: text.bodyMedium)),
                              ],
                            ),
                          )),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: SahlhaSpacing.lg),
              ...units.map((u) {
                final unit = u as Map<String, dynamic>;
                final skills =
                    (unit['skills'] as List? ?? []);
                return Padding(
                  padding: const EdgeInsets.only(
                      bottom: SahlhaSpacing.md),
                  child: SahlhaCard(
                    child: Column(
                      crossAxisAlignment:
                          CrossAxisAlignment.start,
                      children: [
                        Text(unit['title']?.toString() ?? '',
                            style: text.titleMedium),
                        const SizedBox(height: SahlhaSpacing.sm),
                        ...skills.map((s) {
                          final skill = s as Map<String, dynamic>;
                          return Padding(
                            padding: const EdgeInsets.only(
                                bottom: SahlhaSpacing.xs),
                            child: Row(
                              children: [
                                Expanded(
                                    child: Text(
                                        (skill['name'] as String?)
                                                    ?.isNotEmpty ==
                                                true
                                            ? skill['name'] as String
                                            : (skill['skill_id']
                                                    ?.toString() ??
                                                ''),
                                        style:
                                            text.bodyMedium)),
                                SkillStatusBadge(
                                    state: skill['state']
                                            ?.toString() ??
                                        'not_started'),
                              ],
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                );
              }),
            ],
          );
        },
      ),
    );
  }
}

final _studentDetailProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, (String, String)>((ref, ids) {
  return ref
      .watch(teacherRepositoryProvider)
      .studentProgress(ids.$1, ids.$2);
});
