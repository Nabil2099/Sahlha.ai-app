import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../classrooms/data/classroom_repository.dart';

class ClassroomsScreen extends ConsumerWidget {
  const ClassroomsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final rooms = ref.watch(classroomListProvider);
    return Scaffold(
      appBar: const SahlhaAppBar(title: 'My Classrooms'),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: SahlhaColors.teal,
        foregroundColor: Colors.white,
        onPressed: () => context.push('/teacher/classrooms/new'),
        icon: const Icon(Icons.add),
        label: const Text('New classroom'),
      ),
      body: rooms.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(
          message: e.toString(),
          onRetry: () => ref.invalidate(classroomListProvider),
        ),
        data: (list) {
          if (list.isEmpty) {
            return EmptyState(
              title: 'No classrooms yet',
              message: 'Create your first classroom, then share the join code with students.',
              action: SahlhaPrimaryButton(
                label: 'Create classroom',
                onPressed: () => context.push('/teacher/classrooms/new'),
              ),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            itemCount: list.length,
            separatorBuilder: (_, _) =>
                const SizedBox(height: SahlhaSpacing.md),
            itemBuilder: (_, i) {
              final room = list[i];
              return SahlhaCard(
                onTap: () => context.push('/teacher/classrooms/${room.id}'),
                child: Row(
                  children: [
                    Container(
                      width: 52,
                      height: 52,
                      decoration: BoxDecoration(
                        color: SahlhaColors.tealSoft,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: const Icon(
                        Icons.groups_outlined,
                        color: SahlhaColors.teal,
                        size: 28,
                      ),
                    ),
                    const SizedBox(width: SahlhaSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(room.name, style: text.titleMedium),
                          Text(
                            '${room.subject} · ${room.gradeLevel} · ${room.numStudents ?? 0} students',
                            style: text.bodySmall?.copyWith(
                              color: SahlhaColors.muted,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: SahlhaColors.tealFaint,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              'Code: ${room.joinCode}',
                              style: text.labelSmall?.copyWith(
                                color: SahlhaColors.tealDark,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right, color: SahlhaColors.muted),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}
