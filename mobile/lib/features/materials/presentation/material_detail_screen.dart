import 'package:flutter/material.dart' hide Material;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../teacher/domain/bank_models.dart';
import '../data/material_repository.dart';
import '../domain/material.dart';
import 'upload_controller.dart';

/// Teacher: one material — AI processing states, generated skills
/// (review/edit), and question-bank generation + readiness.
class MaterialDetailScreen extends ConsumerWidget {
  const MaterialDetailScreen({
    super.key,
    required this.materialId,
    this.classroomId,
  });

  final String materialId;
  final String? classroomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final material = ref.watch(_materialProvider(materialId));
    final roomId = material.value?.classroomId ?? classroomId;
    void backToClassroom() {
      if (context.canPop()) {
        context.pop();
      } else {
        context.go(
          roomId == null || roomId.isEmpty
              ? '/teacher/classrooms'
              : '/teacher/classrooms/${Uri.encodeComponent(roomId)}?tab=materials',
        );
      }
    }

    ref.listen(uploadControllerProvider, (prev, next) {
      if (prev?.step != next.step ||
          prev?.material?.status != next.material?.status) {
        ref.invalidate(_materialProvider(materialId));
        ref.invalidate(materialSkillsProvider(materialId));
        ref.invalidate(_banksProvider(materialId));
      }
      if (next.error != null && next.error != prev?.error) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(next.error!)));
      }
    });
    return PopScope(
      canPop: context.canPop(),
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) backToClassroom();
      },
      child: Scaffold(
        appBar: SahlhaAppBar(title: 'Material', onBack: backToClassroom),
        body: material.when(
          loading: () => const LoadingState(),
          error: (e, _) => ErrorState(
            message: e.toString(),
            onRetry: () => ref.invalidate(_materialProvider(materialId)),
          ),
          data: (mat) => _Body(material: mat),
        ),
      ),
    );
  }
}

final _materialProvider = FutureProvider.autoDispose.family<Material, String>((
  ref,
  id,
) {
  return ref.watch(materialRepositoryProvider).get(id);
});

class _Body extends ConsumerWidget {
  const _Body({required this.material});

  final Material material;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final upload = ref.watch(uploadControllerProvider);
    final skills = ref.watch(materialSkillsProvider(material.id));
    final banks = ref.watch(_banksProvider(material.id));

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_materialProvider(material.id));
        await ref.read(_materialProvider(material.id).future);
      },
      child: ListView(
        padding: const EdgeInsets.all(SahlhaSpacing.page),
        children: [
          SahlhaCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(material.title, style: text.titleLarge),
                Text(
                  material.filename,
                  style: text.bodySmall?.copyWith(color: SahlhaColors.muted),
                ),
                const SizedBox(height: SahlhaSpacing.sm),
                Text(
                  material.friendlyStatus,
                  style: text.titleMedium?.copyWith(
                    color: SahlhaColors.tealDark,
                  ),
                ),
                if (material.isFailed && material.statusDetail.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    material.statusDetail,
                    style: text.bodyMedium?.copyWith(
                      color: SahlhaColors.danger,
                    ),
                  ),
                ],
                if (upload.step.isNotEmpty) ...[
                  const SizedBox(height: SahlhaSpacing.md),
                  Row(
                    children: [
                      const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: SahlhaColors.teal,
                        ),
                      ),
                      const SizedBox(width: SahlhaSpacing.sm),
                      Expanded(
                        child: Text(upload.step, style: text.bodyMedium),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: SahlhaSpacing.lg),
          // Step 1: skills.
          if (!material.isFailed) ...[
            SahlhaPrimaryButton(
              label: skills.value?.isNotEmpty == true
                  ? 'Re-extract skills'
                  : 'Find learning skills',
              loading: upload.extracting,
              onPressed: upload.extracting || upload.generating
                  ? null
                  : () => ref
                        .read(uploadControllerProvider.notifier)
                        .extractSkills(material.id),
            ),
            const SizedBox(height: SahlhaSpacing.md),
          ],
          Text('Generated skills', style: text.titleLarge),
          const SizedBox(height: SahlhaSpacing.sm),
          skills.when(
            loading: () => const LoadingState(message: 'Reading skills…'),
            error: (e, _) => ErrorState(
              message: e.toString(),
              onRetry: () =>
                  ref.invalidate(materialSkillsProvider(material.id)),
            ),
            data: (list) {
              if (list.isEmpty) {
                return const SahlhaCard(
                  child: Text(
                    'No skills yet. Use “Find learning skills” above.',
                  ),
                );
              }
              return Column(
                children: list
                    .map(
                      (s) => Padding(
                        padding: const EdgeInsets.only(
                          bottom: SahlhaSpacing.sm,
                        ),
                        child: _SkillCard(materialId: material.id, skill: s),
                      ),
                    )
                    .toList(),
              );
            },
          ),
          const SizedBox(height: SahlhaSpacing.lg),
          // Step 2: banks.
          if (skills.value?.isNotEmpty == true) ...[
            SahlhaPrimaryButton(
              label: 'Generate practice questions',
              loading: upload.generating,
              onPressed: upload.extracting || upload.generating
                  ? null
                  : () => ref
                        .read(uploadControllerProvider.notifier)
                        .generateBanks(material.id),
            ),
            const SizedBox(height: SahlhaSpacing.md),
          ],
          Text('Question banks', style: text.titleLarge),
          const SizedBox(height: SahlhaSpacing.sm),
          banks.when(
            loading: () => const LoadingState(message: 'Reading banks…'),
            error: (e, _) => ErrorState(
              message: e.toString(),
              onRetry: () => ref.invalidate(_banksProvider(material.id)),
            ),
            data: (list) {
              if (list.isEmpty) {
                return const SahlhaCard(
                  child: Text(
                    'No question banks yet. Generate practice questions after reviewing the skills.',
                  ),
                );
              }
              return Column(
                children: list
                    .map(
                      (b) => Padding(
                        padding: const EdgeInsets.only(
                          bottom: SahlhaSpacing.sm,
                        ),
                        child: _BankCard(bank: b),
                      ),
                    )
                    .toList(),
              );
            },
          ),
        ],
      ),
    );
  }
}

final _banksProvider = FutureProvider.autoDispose
    .family<List<BankSummary>, String>((ref, id) {
      return ref.watch(materialRepositoryProvider).banks(id);
    });

class _SkillCard extends ConsumerWidget {
  const _SkillCard({required this.materialId, required this.skill});

  final String materialId;
  final GeneratedSkill skill;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return SahlhaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.check_circle,
                color: SahlhaColors.teal,
                size: 20,
              ),
              const SizedBox(width: SahlhaSpacing.sm),
              Expanded(
                child: Text(
                  skill.name.isEmpty ? skill.skillId : skill.name,
                  style: text.titleMedium,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.edit_outlined, size: 20),
                onPressed: () => _edit(context, ref),
              ),
            ],
          ),
          if (skill.description.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                skill.description,
                style: text.bodyMedium?.copyWith(color: SahlhaColors.muted),
              ),
            ),
          const SizedBox(height: 4),
          Text(
            skill.bankStatus == 'approved'
                ? 'Practice approved (${skill.approvedQuestions} questions)'
                : skill.bankStatus == 'pending'
                ? 'Practice pending your review'
                : 'No practice yet',
            style: text.bodySmall?.copyWith(
              color: skill.bankStatus == 'approved'
                  ? SahlhaColors.success
                  : SahlhaColors.muted,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _edit(BuildContext context, WidgetRef ref) async {
    final name = TextEditingController(text: skill.name);
    final desc = TextEditingController(text: skill.description);
    final ok = await showSahlhaSheet<bool>(
      context,
      Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('Edit skill', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: SahlhaSpacing.md),
          TextField(
            controller: name,
            decoration: const InputDecoration(labelText: 'Name'),
          ),
          const SizedBox(height: SahlhaSpacing.sm),
          TextField(
            controller: desc,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Description'),
          ),
          const SizedBox(height: SahlhaSpacing.md),
          SahlhaPrimaryButton(
            label: 'Save',
            onPressed: () => Navigator.of(context).pop(true),
          ),
        ],
      ),
    );
    if (ok == true && context.mounted) {
      try {
        await ref
            .read(materialRepositoryProvider)
            .updateSkill(
              materialId,
              skill.skillId,
              name: name.text.trim(),
              description: desc.text.trim(),
            );
        ref.invalidate(materialSkillsProvider(materialId));
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(e.toString())));
        }
      }
    }
    name.dispose();
    desc.dispose();
  }
}

class _BankCard extends StatelessWidget {
  const _BankCard({required this.bank});

  final BankSummary bank;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SahlhaCard(
      onTap: bank.id == null
          ? null
          : () => context.push('/teacher/banks/${bank.id}'),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(bank.skillId, style: text.titleMedium),
                Text(
                  'v${bank.version} · ${bank.numQuestions} questions',
                  style: text.bodySmall?.copyWith(color: SahlhaColors.muted),
                ),
              ],
            ),
          ),
          _BankStatusChip(status: bank.status),
        ],
      ),
    );
  }
}

class _BankStatusChip extends StatelessWidget {
  const _BankStatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    final String label;
    switch (status) {
      case 'approved':
        bg = SahlhaColors.successSoft;
        fg = SahlhaColors.success;
        label = 'Approved';
      case 'rejected':
        bg = SahlhaColors.dangerSoft;
        fg = SahlhaColors.danger;
        label = 'Rejected';
      default:
        bg = SahlhaColors.sunSoft;
        fg = const Color(0xFFB45309);
        label = 'Pending review';
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall
            ?.copyWith(color: fg, fontWeight: FontWeight.w800),
      ),
    );
  }
}
