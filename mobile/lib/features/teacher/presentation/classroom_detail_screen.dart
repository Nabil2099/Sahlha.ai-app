import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../classrooms/data/classroom_repository.dart';
import '../../classrooms/domain/classroom.dart';
import '../../materials/data/material_repository.dart';
import '../../materials/domain/material.dart';
import '../data/teacher_repository.dart';

/// Classroom detail with tabs: Students / Materials / Insights.
class ClassroomDetailScreen extends ConsumerStatefulWidget {
  const ClassroomDetailScreen({super.key, required this.classroomId});

  final String classroomId;

  @override
  ConsumerState<ClassroomDetailScreen> createState() =>
      _ClassroomDetailScreenState();
}

class _ClassroomDetailScreenState
    extends ConsumerState<ClassroomDetailScreen> {
  @override
  Widget build(BuildContext context) {
    final roomAsync = ref.watch(_classroomProvider(widget.classroomId));
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: roomAsync.whenOrNull(
                  data: (r) => Text(r.name,
                      style: Theme.of(context).textTheme.titleLarge)) ??
              const Text('Classroom'),
          bottom: const TabBar(
            labelColor: SahlhaColors.tealDark,
            unselectedLabelColor: SahlhaColors.muted,
            indicatorColor: SahlhaColors.teal,
            tabs: [
              Tab(text: 'Students'),
              Tab(text: 'Materials'),
              Tab(text: 'Insights'),
            ],
          ),
        ),
        body: roomAsync.when(
          loading: () => const LoadingState(),
          error: (e, _) => ErrorState(
              message: e.toString(),
              onRetry: () => ref.invalidate(
                  _classroomProvider(widget.classroomId))),
          data: (room) => TabBarView(
            children: [
              _StudentsTab(classroomId: room.id),
              _MaterialsTab(classroomId: room.id, joinCode: room.joinCode),
              _InsightsTab(classroomId: room.id),
            ],
          ),
        ),
      ),
    );
  }
}

final _classroomProvider = FutureProvider.autoDispose
    .family<Classroom, String>((ref, id) {
  return ref.watch(classroomRepositoryProvider).get(id);
});

class _StudentsTab extends ConsumerWidget {
  const _StudentsTab({required this.classroomId});

  final String classroomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final students = ref.watch(
        _studentsProvider(classroomId));
    final mastery =
        ref.watch(classroomMasteryProvider(classroomId));
    return students.when(
      loading: () => const LoadingState(),
      error: (e, _) => ErrorState(
          message: e.toString(),
          onRetry: () =>
              ref.invalidate(_studentsProvider(classroomId))),
      data: (list) {
        if (list.isEmpty) {
          return EmptyState(
            title: 'No students yet',
            message:
                'Share the classroom join code (Materials tab shows it too) so students can join.',
          );
        }
        final states = <String, String>{};
        for (final s
            in (mastery.valueOrNull?['students'] as List? ?? [])) {
          final m = s as Map<String, dynamic>;
          final summary =
              (m['summary'] as Map?)?.cast<String, dynamic>() ?? {};
          final needs =
              (summary['needs_practice'] as num?)?.toInt() ?? 0;
          final mastering =
              (summary['mastered'] as num?)?.toInt() ?? 0;
          states[m['student_id'].toString()] =
              needs > 0 ? 'needs_practice' : (mastering > 0 ? 'developing' : 'not_started');
        }
        return ListView.separated(
          padding: const EdgeInsets.all(SahlhaSpacing.page),
          itemCount: list.length,
          separatorBuilder: (_, __) =>
              const SizedBox(height: SahlhaSpacing.sm),
          itemBuilder: (_, i) {
            final s = list[i];
            return SahlhaCard(
              onTap: () => context.push(
                  '/teacher/students/$classroomId/${s.id}'),
              padding: const EdgeInsets.all(SahlhaSpacing.md),
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: const BoxDecoration(
                        color: SahlhaColors.tealSoft,
                        shape: BoxShape.circle),
                    child: Center(
                        child: Text(
                            s.name.isEmpty
                                ? '?'
                                : s.name[0].toUpperCase(),
                            style: text.titleMedium?.copyWith(
                                color: SahlhaColors.tealDark))),
                  ),
                  const SizedBox(width: SahlhaSpacing.md),
                  Expanded(
                      child: Text(s.name,
                          style: text.titleMedium)),
                  SkillStatusBadge(
                      state: states[s.id] ?? 'not_started'),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

final _studentsProvider = FutureProvider.autoDispose
    .family<List<ClassroomStudent>, String>((ref, id) {
  return ref.watch(classroomRepositoryProvider).students(id);
});

class _MaterialsTab extends ConsumerWidget {
  const _MaterialsTab({required this.classroomId, required this.joinCode});

  final String classroomId;
  final String joinCode;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final materials = ref.watch(
        materialListProvider(classroomId: classroomId));
    return materials.when(
      loading: () => const LoadingState(),
      error: (e, _) => ErrorState(
          message: e.toString(),
          onRetry: () => ref.invalidate(
              materialListProvider(classroomId: classroomId))),
      data: (list) => ListView(
        padding: const EdgeInsets.all(SahlhaSpacing.page),
        children: [
          SahlhaCard(
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Text('Classroom join code',
                          style: text.bodySmall?.copyWith(
                              color: SahlhaColors.muted)),
                      Text(joinCode,
                          style: text.headlineSmall?.copyWith(
                              letterSpacing: 3,
                              color: SahlhaColors.tealDark)),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.copy_outlined),
                  onPressed: () {
                    Clipboard.setData(
                        ClipboardData(text: joinCode));
                    ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                            content:
                                Text('Join code copied')));
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: SahlhaSpacing.md),
          SahlhaPrimaryButton(
            label: 'Add material',
            onPressed: () => context.push(
                '/teacher/materials/new?classroomId=$classroomId'),
          ),
          const SizedBox(height: SahlhaSpacing.lg),
          if (list.isEmpty)
            const EmptyState(
              title: 'No materials yet',
              message:
                  'Upload your curriculum (PDF, DOCX, PPTX, TXT, images). Sahlha will find the skills and draft practice.',
            )
          else
            ...list.map((m) => Padding(
                  padding: const EdgeInsets.only(
                      bottom: SahlhaSpacing.sm),
                  child: _MaterialCard(material: m),
                )),
        ],
      ),
    );
  }
}

class _MaterialCard extends StatelessWidget {
  const _MaterialCard({required this.material});

  final Material material;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SahlhaCard(
      onTap: () =>
          context.push('/teacher/materials/${material.id}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                  child: Text(material.title,
                      style: text.titleMedium)),
              _StatusChip(status: material.status),
            ],
          ),
          const SizedBox(height: 4),
          Text(material.filename,
              style: text.bodySmall
                  ?.copyWith(color: SahlhaColors.muted)),
          const SizedBox(height: SahlhaSpacing.sm),
          Text(
            '${material.numSkills} skills · ${material.approvedBanks}/${material.numBanks} banks approved',
            style: text.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    final String label;
    switch (status) {
      case 'banks_ready':
        bg = SahlhaColors.successSoft;
        fg = SahlhaColors.success;
        label = 'Practice ready';
      case 'skills_ready':
        bg = SahlhaColors.tealSoft;
        fg = SahlhaColors.tealDark;
        label = 'Skills ready';
      case 'failed':
        bg = SahlhaColors.dangerSoft;
        fg = SahlhaColors.danger;
        label = 'Needs attention';
      case 'processing':
        bg = SahlhaColors.sunSoft;
        fg = const Color(0xFFB45309);
        label = 'Processing…';
      default:
        bg = SahlhaColors.tealFaint;
        fg = SahlhaColors.tealDark;
        label = 'Uploaded';
    }
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
          color: bg, borderRadius: BorderRadius.circular(99)),
      child: Text(label,
          style: Theme.of(context)
              .textTheme
              .labelSmall
              ?.copyWith(color: fg, fontWeight: FontWeight.w800)),
    );
  }
}

class _InsightsTab extends ConsumerWidget {
  const _InsightsTab({required this.classroomId});

  final String classroomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final mastery =
        ref.watch(classroomMasteryProvider(classroomId));
    return mastery.when(
      loading: () => const LoadingState(),
      error: (e, _) => ErrorState(
          message: e.toString(),
          onRetry: () => ref.invalidate(
              classroomMasteryProvider(classroomId))),
      data: (data) {
        final skills =
            (data['skill_performance'] as List? ?? []);
        if (skills.isEmpty) {
          return const EmptyState(
            title: 'No insights yet',
            message:
                'Insights appear once students start practicing.',
          );
        }
        return ListView(
          padding: const EdgeInsets.all(SahlhaSpacing.page),
          children: [
            Text('Which skill is difficult?',
                style: text.titleLarge),
            const SizedBox(height: SahlhaSpacing.sm),
            ...skills.map((s) {
              final skill = s as Map<String, dynamic>;
              final rate =
                  (skill['mastery_rate'] as num?)?.toDouble();
              return Padding(
                padding: const EdgeInsets.only(
                    bottom: SahlhaSpacing.sm),
                child: SahlhaCard(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Text(
                          (skill['name'] as String?)?.isNotEmpty ==
                                  true
                              ? skill['name'] as String
                              : (skill['skill_id']?.toString() ??
                                  ''),
                          style: text.titleMedium),
                      const SizedBox(height: SahlhaSpacing.sm),
                      SahlhaProgressBar(
                          value: rate ?? 0, height: 8),
                      const SizedBox(height: 4),
                      Text(
                        rate == null
                            ? 'Not attempted yet'
                            : '${(rate * 100).round()}% of students mastered · ${skill['attempted']} attempts',
                        style: text.bodySmall?.copyWith(
                            color: SahlhaColors.muted),
                      ),
                    ],
                  ),
                ),
              );
            }),
          ],
        );
      },
    );
  }
}
