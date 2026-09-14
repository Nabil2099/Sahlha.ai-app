import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../classrooms/data/classroom_repository.dart';
import '../data/student_repository.dart';

/// The Sahlha Learning Path: a calm vertical progression
/// (Unit -> Skill -> Practice -> Mastery). Original Sahlha visual language.
class LearnScreen extends ConsumerWidget {
  const LearnScreen({super.key, this.classroomId, this.supplementary = false});

  final String? classroomId;
  final bool supplementary;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (supplementary) {
      return Scaffold(
        appBar: const SahlhaAppBar(title: 'Extra Practice'),
        body: _PathBody(classroomId: null, supplementary: true),
      );
    }
    final roomsAsync = ref.watch(classroomListProvider);
    final text = Theme.of(context).textTheme;

    return Scaffold(
      appBar: const SahlhaAppBar(title: 'My Learning Path'),
      body: roomsAsync.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(
            message: e.toString(),
            onRetry: () => ref.invalidate(classroomListProvider)),
        data: (rooms) {
          if (rooms.isEmpty) {
            return EmptyState(
              title: 'No classroom yet',
              message: 'Join a classroom with your teacher’s code to see your path.',
              action: SahlhaPrimaryButton(
                label: 'Join a classroom',
                onPressed: () => context.push('/student/join'),
              ),
            );
          }
          final selected = classroomId != null
              ? rooms.where((r) => r.id == classroomId).firstOrNull ?? rooms.first
              : rooms.first;
          return Column(
            children: [
              if (rooms.length > 1)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                  child: DropdownButtonFormField<String>(
                    initialValue: selected.id,
                    decoration: const InputDecoration(labelText: 'Classroom'),
                    items: rooms
                        .map((r) => DropdownMenuItem(
                            value: r.id,
                            child: Text('${r.name} · ${r.subject}')))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) context.go('/student/learn?classroomId=$v');
                    },
                  ),
                ),
              Expanded(child: _PathBody(classroomId: selected.id)),
              Padding(
                padding: const EdgeInsets.all(SahlhaSpacing.page),
                child: Text('Where am I? What did I finish? What comes next?',
                    style: text.bodySmall
                        ?.copyWith(color: SahlhaColors.muted),
                    textAlign: TextAlign.center),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _PathBody extends ConsumerWidget {
  const _PathBody({this.classroomId, this.supplementary = false});

  final String? classroomId;
  final bool supplementary;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final path = ref.watch(studentLearningPathProvider(
        classroomId: classroomId, supplementary: supplementary));
    return path.when(
      loading: () => const LoadingState(message: 'Building your path…'),
      error: (e, _) => ErrorState(
          message: e.toString(),
          onRetry: () => ref.invalidate(studentLearningPathProvider(
              classroomId: classroomId,
              supplementary: supplementary))),
      data: (data) {
        final units = (data['units'] as List? ?? []);
        final current = data['current'] as Map<String, dynamic>?;
        if (units.isEmpty) {
          return EmptyState(
            title: supplementary
                ? 'No extra practice yet'
                : 'Your path is being prepared',
            message: supplementary
                ? 'Extra practice from your family will show up here.'
                : 'Your teacher is getting lessons ready. Check back soon.',
          );
        }
        final currentSkill = current?['skill_id']?.toString();
        bool currentSeen = false;
        return ListView.builder(
          padding: const EdgeInsets.all(SahlhaSpacing.page),
          itemCount: units.length,
          itemBuilder: (_, ui) {
            final unit = units[ui] as Map<String, dynamic>;
            final skills = (unit['skills'] as List? ?? []);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Unit ${ui + 1} · ${unit['title'] ?? ''}',
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: SahlhaSpacing.md),
                ...List.generate(skills.length, (i) {
                  final s = skills[i] as Map<String, dynamic>;
                  final state = s['state']?.toString() ?? 'not_started';
                  final isCurrent = s['skill_id'] == currentSkill && !currentSeen;
                  if (isCurrent) currentSeen = true;
                  final node = state == 'mastered'
                      ? PathNodeState.completed
                      : isCurrent
                          ? PathNodeState.current
                          : (currentSeen
                              ? PathNodeState.locked
                              : PathNodeState.upcoming);
                  final subtitle = switch (state) {
                    'mastered' => 'Completed — nicely done',
                    'developing' => 'Developing — keep going',
                    'needs_practice' => 'Needs practice',
                    _ => (s['exercise_ready'] == true
                        ? 'Ready to learn'
                        : 'Coming soon'),
                  };
                  return LearningPathNode(
                    state: node,
                    title: (s['name'] as String?)?.isNotEmpty == true
                        ? s['name'] as String
                        : (s['skill_id']?.toString() ?? 'Skill'),
                    subtitle: subtitle,
                    isLast: i == skills.length - 1,
                    onTap: () {
                      final base =
                          '/student/skill/${s['skill_id']}?materialId=${unit['material_id']}';
                      context.push(supplementary
                          ? '$base&supplementary=true'
                          : '$base&classroomId=$classroomId');
                    },
                  );
                }),
                const SizedBox(height: SahlhaSpacing.lg),
              ],
            );
          },
        );
      },
    );
  }
}
