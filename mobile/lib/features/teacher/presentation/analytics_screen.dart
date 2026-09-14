import 'package:fl_chart/fl_chart.dart';
import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../classrooms/data/classroom_repository.dart';
import '../data/teacher_repository.dart';

/// Class analytics focused on skill-level decisions:
/// which skill is difficult, who needs support. One chart, with purpose.
class AnalyticsScreen extends ConsumerStatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  ConsumerState<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends ConsumerState<AnalyticsScreen> {
  String? _classroomId;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final rooms = ref.watch(classroomListProvider);
    return Scaffold(
      appBar: const SahlhaAppBar(title: 'Analytics'),
      body: rooms.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(
            message: e.toString(),
            onRetry: () => ref.invalidate(classroomListProvider)),
        data: (list) {
          if (list.isEmpty) {
            return EmptyState(
              title: 'No classrooms yet',
              message: 'Create a classroom to see analytics.',
              action: SahlhaPrimaryButton(
                label: 'Create classroom',
                onPressed: () =>
                    context.push('/teacher/classrooms/new'),
              ),
            );
          }
          final selected = list
                  .where((r) => r.id == _classroomId)
                  .firstOrNull ??
              list.first;
          return ListView(
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            children: [
              DropdownButtonFormField<String>(
                initialValue: selected.id,
                decoration:
                    const InputDecoration(labelText: 'Classroom'),
                items: list
                    .map((r) => DropdownMenuItem(
                        value: r.id, child: Text(r.name)))
                    .toList(),
                onChanged: (v) =>
                    setState(() => _classroomId = v),
              ),
              const SizedBox(height: SahlhaSpacing.lg),
              _AnalyticsBody(classroomId: selected.id),
              const SizedBox(height: SahlhaSpacing.sm),
              Text(
                'Charts support a decision: which skill to teach again, and who needs support.',
                style: text.bodySmall
                    ?.copyWith(color: SahlhaColors.muted),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _AnalyticsBody extends ConsumerWidget {
  const _AnalyticsBody({required this.classroomId});

  final String classroomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final mastery = ref.watch(classroomMasteryProvider(classroomId));
    return mastery.when(
      loading: () => const LoadingState(),
      error: (e, _) => ErrorState(
          message: e.toString(),
          onRetry: () =>
              ref.invalidate(classroomMasteryProvider(classroomId))),
      data: (data) {
        final skills = (data['skill_performance'] as List? ?? [])
            .cast<Map<String, dynamic>>();
        final needing = (data['needing_support'] as List? ?? []);
        if (skills.isEmpty) {
          return const EmptyState(
            title: 'No data yet',
            message:
                'Skill analytics appear once students start practicing.',
          );
        }
        final chartSkills = skills.take(6).toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Skill mastery', style: text.titleLarge),
            const SizedBox(height: SahlhaSpacing.sm),
            SahlhaCard(
              child: SizedBox(
                height: 220,
                child: BarChart(
                  BarChartData(
                    gridData: const FlGridData(show: false),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      topTitles: const AxisTitles(
                          sideTitles: SideTitles(showTitles: false)),
                      rightTitles: const AxisTitles(
                          sideTitles: SideTitles(showTitles: false)),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 36,
                          getTitlesWidget: (v, _) => Text(
                              '${v.toInt()}%',
                              style: text.labelSmall?.copyWith(
                                  color: SahlhaColors.muted)),
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 60,
                          getTitlesWidget: (v, _) {
                            final i = v.toInt();
                            if (i < 0 || i >= chartSkills.length) {
                              return const SizedBox.shrink();
                            }
                            final name = ((chartSkills[i]['name']
                                            as String?)
                                        ?.isNotEmpty ==
                                    true)
                                ? chartSkills[i]['name'] as String
                                : (chartSkills[i]['skill_id']
                                        ?.toString() ??
                                    '');
                            final short = name.length > 10
                                ? '${name.substring(0, 10)}…'
                                : name;
                            return Padding(
                              padding:
                                  const EdgeInsets.only(top: 6),
                              child: Text(short,
                                  style: text.labelSmall?.copyWith(
                                      color: SahlhaColors.muted)),
                            );
                          },
                        ),
                      ),
                    ),
                    minY: 0,
                    maxY: 100,
                    barGroups: List.generate(chartSkills.length,
                        (i) {
                      final rate =
                          (chartSkills[i]['mastery_rate'] as num?)
                                  ?.toDouble() ??
                              0;
                      return BarChartGroupData(
                        x: i,
                        barRods: [
                          BarChartRodData(
                            toY: rate * 100,
                            width: 22,
                            borderRadius: const BorderRadius.vertical(
                                top: Radius.circular(8)),
                            color: rate >= 0.8
                                ? SahlhaColors.success
                                : rate >= 0.6
                                    ? SahlhaColors.teal
                                    : SahlhaColors.sun,
                          ),
                        ],
                      );
                    }),
                  ),
                ),
              ),
            ),
            const SizedBox(height: SahlhaSpacing.lg),
            Text('Students needing support (${needing.length})',
                style: text.titleLarge),
            const SizedBox(height: SahlhaSpacing.sm),
            if (needing.isEmpty)
              const SahlhaCard(
                  child: Text('Everyone is on track right now.'))
            else
              ...needing.map((n) {
                final item = n as Map<String, dynamic>;
                return Padding(
                  padding: const EdgeInsets.only(
                      bottom: SahlhaSpacing.sm),
                  child: SahlhaCard(
                    onTap: () => context.push(
                        '/teacher/students/$classroomId/${item['student_id']}'),
                    padding:
                        const EdgeInsets.all(SahlhaSpacing.md),
                    child: Row(
                      children: [
                        Expanded(
                            child: Text(
                                item['name']?.toString() ?? '',
                                style: text.titleMedium)),
                        const SkillStatusBadge(
                            state: 'needs_practice'),
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
