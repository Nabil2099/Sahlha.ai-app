import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/auth_controller.dart';
import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import '../../learning_profile/data/learning_profile_repository.dart';

/// Secondary student features live here (NOT in the bottom navigation).
class StudentProfileScreen extends ConsumerWidget {
  const StudentProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final user = ref.watch(currentUserProvider);
    final profile = ref.watch(learningProfileProvider);

    return Scaffold(
      appBar: const SahlhaAppBar(title: 'Profile'),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(SahlhaSpacing.page),
          children: [
            SahlhaCard(
              child: Row(
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    decoration: const BoxDecoration(
                        color: SahlhaColors.tealSoft,
                        shape: BoxShape.circle),
                    child: const Icon(Icons.school_outlined,
                        color: SahlhaColors.teal, size: 30),
                  ),
                  const SizedBox(width: SahlhaSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(user?.name ?? '',
                            style: text.titleLarge),
                        Text(user?.email ?? '',
                            style: text.bodySmall?.copyWith(
                                color: SahlhaColors.muted)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: SahlhaSpacing.lg),
            profile.whenOrNull(
                  data: (p) => SahlhaCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Parent link code',
                            style: text.titleMedium),
                        const SizedBox(height: 4),
                        Text(
                          'Share this code with a parent so they can follow your progress.',
                          style: text.bodySmall?.copyWith(
                              color: SahlhaColors.muted),
                        ),
                        const SizedBox(height: SahlhaSpacing.sm),
                        Row(
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 14, vertical: 12),
                                decoration: BoxDecoration(
                                  color: SahlhaColors.tealFaint,
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                      color: SahlhaColors.tealSoft),
                                ),
                                child: Text(
                                  p.linkCode.isEmpty
                                      ? '—'
                                      : p.linkCode,
                                  style: text.titleLarge?.copyWith(
                                      letterSpacing: 3,
                                      color: SahlhaColors.tealDark),
                                ),
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.copy_outlined),
                              onPressed: p.linkCode.isEmpty
                                  ? null
                                  : () {
                                      Clipboard.setData(ClipboardData(
                                          text: p.linkCode));
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(const SnackBar(
                                              content: Text(
                                                  'Code copied')));
                                    },
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ) ??
                const SizedBox.shrink(),
            const SizedBox(height: SahlhaSpacing.lg),
            _Tile(
              icon: Icons.group_add_outlined,
              title: 'Join a classroom',
              onTap: () => context.push('/student/join'),
            ),
            _Tile(
              icon: Icons.tune_outlined,
              title: 'How I learn best',
              subtitle: 'Review your learning preferences',
              onTap: () => context.push('/student/setup'),
            ),
            _Tile(
              icon: Icons.logout_outlined,
              title: 'Log out',
              onTap: () async {
                await ref
                    .read(authControllerProvider.notifier)
                    .logout();
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.icon, required this.title, this.subtitle, this.onTap});

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: SahlhaSpacing.sm),
      child: SahlhaCard(
        onTap: onTap,
        padding: const EdgeInsets.all(SahlhaSpacing.md),
        child: Row(
          children: [
            Icon(icon, color: SahlhaColors.teal),
            const SizedBox(width: SahlhaSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: Theme.of(context).textTheme.titleMedium),
                  if (subtitle != null)
                    Text(subtitle!,
                        style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: SahlhaColors.muted),
          ],
        ),
      ),
    );
  }
}
