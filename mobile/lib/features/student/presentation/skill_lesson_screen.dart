import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../../../core/audio/audio_service.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../data/student_repository.dart';
import '../domain/skill_models.dart';
import 'practice_controller.dart';

/// One skill at a time: short explanation, key idea, one primary action,
/// and a single "Help me" entry point.
class SkillLessonScreen extends ConsumerWidget {
  const SkillLessonScreen({
    super.key,
    required this.skillId,
    required this.materialId,
    this.classroomId,
    this.supplementary = false,
  });

  final String skillId;
  final String materialId;
  final String? classroomId;
  final bool supplementary;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final bundle = ref.watch(studentSkillBundleProvider(
      skillId: skillId,
      materialId: materialId,
      classroomId: classroomId,
      supplementary: supplementary,
    ));
    return Scaffold(
      appBar: const SahlhaAppBar(title: 'Lesson'),
      body: bundle.when(
        loading: () => const LoadingState(message: 'Opening your lesson…'),
        error: (e, _) => ErrorState(
            message: e.toString(),
            onRetry: () => ref.invalidate(studentSkillBundleProvider(
                skillId: skillId,
                materialId: materialId,
                classroomId: classroomId,
                supplementary: supplementary))),
        data: (skill) => SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(SahlhaSpacing.page),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Skill ${skill.position} of ${skill.total}',
                    style: text.bodySmall
                        ?.copyWith(color: SahlhaColors.muted)),
                const SizedBox(height: SahlhaSpacing.sm),
                SahlhaProgressBar(value: skill.position / skill.total),
                const SizedBox(height: SahlhaSpacing.lg),
                Row(
                  children: [
                    Expanded(
                        child: Text(skill.name, style: text.headlineSmall)),
                    const SizedBox(width: SahlhaSpacing.sm),
                    SkillStatusBadge(state: skill.state),
                  ],
                ),
                const SizedBox(height: SahlhaSpacing.md),
                if (skill.hasImage) ...[
                  _SkillImage(
                      skillId: skillId,
                      materialId: materialId,
                      classroomId: classroomId,
                      supplementary: supplementary),
                  const SizedBox(height: SahlhaSpacing.md),
                ],
                Text(
                  skill.explanation.isEmpty
                      ? skill.description
                      : skill.explanation,
                  style: text.bodyLarge,
                ),
                if (skill.keyConcepts.isNotEmpty) ...[
                  const SizedBox(height: SahlhaSpacing.lg),
                  Text('Key ideas', style: text.titleMedium),
                  const SizedBox(height: SahlhaSpacing.sm),
                  ...skill.keyConcepts.map((c) => Padding(
                        padding: const EdgeInsets.only(
                            bottom: SahlhaSpacing.xs),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(Icons.check,
                                size: 18, color: SahlhaColors.teal),
                            const SizedBox(width: SahlhaSpacing.sm),
                            Expanded(
                                child: Text(c, style: text.bodyMedium)),
                          ],
                        ),
                      )),
                ],
                const SizedBox(height: SahlhaSpacing.xl),
                SahlhaPrimaryButton(
                  label: skill.exerciseReady ? 'Practice this skill' : 'Practice (coming soon)',
                  onPressed: skill.exerciseReady
                      ? () {
                          ref.read(practiceControllerProvider.notifier).reset();
                          context.push(
                              '/student/practice?classroomId=${classroomId ?? ''}&materialId=$materialId&skillId=$skillId&supplementary=$supplementary');
                        }
                      : null,
                ),
                const SizedBox(height: SahlhaSpacing.sm),
                SizedBox(
                  width: double.infinity,
                  child: SahlhaSecondaryButton(
                    label: 'Help me',
                    onPressed: () => _openHelp(context, ref, skill),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _openHelp(
      BuildContext context, WidgetRef ref, SkillBundle skill) async {
    final order = skill.helpOrder;
    final first = order.take(3).toList();
    final rest = order.skip(3).toList();
    var showMore = false;
    await showSahlhaSheet<void>(
      context,
      StatefulBuilder(
        builder: (ctx, setSheet) => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('How can I help?',
                style: Theme.of(ctx).textTheme.titleLarge),
            const SizedBox(height: SahlhaSpacing.md),
            ...first.map((kind) => Padding(
                  padding:
                      const EdgeInsets.only(bottom: SahlhaSpacing.sm),
                  child: _HelpButton(
                    kind: kind,
                    onTap: () {
                      Navigator.of(ctx).pop();
                      _showHelp(context, ref, kind);
                    },
                  ),
                )),
            if (!showMore)
              TextButton(
                onPressed: () => setSheet(() => showMore = true),
                child: const Text('More ways to help'),
              ),
            if (showMore)
              ...rest.map((kind) => Padding(
                    padding:
                        const EdgeInsets.only(bottom: SahlhaSpacing.sm),
                    child: _HelpButton(
                      kind: kind,
                      onTap: () {
                        Navigator.of(ctx).pop();
                        _showHelp(context, ref, kind);
                      },
                    ),
                  )),
          ],
        ),
      ),
    );
  }

  Future<void> _showHelp(
      BuildContext context, WidgetRef ref, String kind) async {
    if (kind == 'read_aloud') {
      final url = ref.read(studentRepositoryProvider).skillAudioUrl(
          skillId: skillId,
          materialId: materialId,
          classroomId: classroomId,
          supplementary: supplementary);
      final err = await ref.read(audioServiceProvider).playUrl(url);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(err ?? 'Playing your lesson…'),
            duration: const Duration(seconds: 2)));
      }
      return;
    }
    if (!context.mounted) return;
    showSahlhaSheet<void>(
      context,
      FutureBuilder<SkillHelp>(
        future: ref.read(studentRepositoryProvider).skillHelp(
            skillId: skillId,
            materialId: materialId,
            kind: kind,
            classroomId: classroomId,
            supplementary: supplementary),
        builder: (ctx, snap) {
          final text = Theme.of(ctx).textTheme;
          if (snap.connectionState == ConnectionState.waiting) {
            return const Padding(
              padding: EdgeInsets.all(24),
              child: LoadingState(message: 'Preparing help…'),
            );
          }
          if (snap.hasError || snap.data == null) {
            return Padding(
              padding: const EdgeInsets.all(8),
              child: Text('Help is unavailable right now. Try again soon.',
                  style: text.bodyMedium),
            );
          }
          final help = snap.data!;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(help.title, style: text.titleLarge),
              const SizedBox(height: SahlhaSpacing.sm),
              if (help.steps.isNotEmpty)
                ...help.steps.map((s) => Padding(
                      padding: const EdgeInsets.only(
                          bottom: SahlhaSpacing.sm),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.arrow_right,
                              color: SahlhaColors.teal),
                          Expanded(
                              child: Text(s, style: text.bodyMedium)),
                        ],
                      ),
                    )),
              if (help.steps.isEmpty)
                Text(help.body, style: text.bodyLarge),
              if (help.keyConcepts.isNotEmpty) ...[
                const SizedBox(height: SahlhaSpacing.md),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: help.keyConcepts
                      .map((c) => Chip(
                            label: Text(c),
                            backgroundColor: SahlhaColors.tealSoft,
                            side: BorderSide.none,
                          ))
                      .toList(),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _HelpButton extends StatelessWidget {
  const _HelpButton({required this.kind, required this.onTap});

  final String kind;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final label = switch (kind) {
      'simpler' => 'Make it simpler',
      'example' => 'Show an example',
      'read_aloud' => 'Read aloud',
      'steps' => 'Break into steps',
      'visual' => 'Show visually',
      'word' => 'Explain this word',
      _ => kind,
    };
    final icon = switch (kind) {
      'simpler' => Icons.simplify_outlined,
      'example' => Icons.lightbulb_outline,
      'read_aloud' => Icons.volume_up_outlined,
      'steps' => Icons.format_list_numbered_outlined,
      'visual' => Icons.image_outlined,
      'word' => Icons.spellcheck_outlined,
      _ => Icons.help_outline,
    };
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon),
      label: Align(alignment: Alignment.centerLeft, child: Text(label)),
      style: OutlinedButton.styleFrom(
          alignment: Alignment.centerLeft,
          minimumSize: const Size.fromHeight(52)),
    );
  }
}

/// Authenticated image load (backend requires a bearer token).
class _SkillImage extends ConsumerWidget {
  const _SkillImage({
    required this.skillId,
    required this.materialId,
    this.classroomId,
    this.supplementary = false,
  });

  final String skillId;
  final String materialId;
  final String? classroomId;
  final bool supplementary;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final url = ref.watch(studentRepositoryProvider).skillImageUrl(
        skillId: skillId,
        materialId: materialId,
        classroomId: classroomId,
        supplementary: supplementary);
    return FutureBuilder<Response<List<int>>>(
      future: ref.watch(apiClientProvider).dio.get<List<int>>(url,
          options: Options(responseType: ResponseType.bytes)),
      builder: (_, snap) {
        if (snap.data?.data == null) return const SizedBox.shrink();
        return ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Image.memory(
            Uint8List.fromList(snap.data!.data!),
            height: 180,
            width: double.infinity,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => const SizedBox.shrink(),
          ),
        );
      },
    );
  }
}
