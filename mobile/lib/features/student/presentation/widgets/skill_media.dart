import 'audio_companion.dart';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/audio/audio_service.dart';
import '../../../../core/theme/sahlha_colors.dart';
import '../../data/student_repository.dart';

/// Structured placeholder while a lesson opens: title bar, reading card
/// shape and action shapes, so the layout does not jump when content lands.
class LessonSkeleton extends StatelessWidget {
  const LessonSkeleton({super.key});
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Opening your lesson',
    child: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
        children: [
          Container(
            height: 12,
            width: 140,
            decoration: BoxDecoration(
              color: SahlhaColors.tealSoft,
              borderRadius: BorderRadius.circular(6),
            ),
          ),
          const SizedBox(height: 12),
          Container(
            height: 10,
            decoration: BoxDecoration(
              color: SahlhaColors.borderSubtle,
              borderRadius: BorderRadius.circular(6),
            ),
          ),
          const SizedBox(height: 24),
          Container(
            height: 30,
            width: 220,
            decoration: BoxDecoration(
              color: SahlhaColors.tealSoft,
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          const SizedBox(height: 20),
          Container(
            height: 220,
            decoration: BoxDecoration(
              color: SahlhaColors.surfaceRaised,
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: SahlhaColors.borderSubtle),
            ),
          ),
          const SizedBox(height: 20),
          Container(
            height: 54,
            decoration: BoxDecoration(
              color: SahlhaColors.tealSoft,
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ],
      ),
    ),
  );
}

/// A calm supporting visual for one skill: rounded corners, soft border and
/// shadow, gentle fade-in, skeleton while loading. Renders nothing at all
/// when the backend has no image — the lesson simply continues.
class SkillVisualCard extends ConsumerWidget {
  const SkillVisualCard({
    super.key,
    required this.skillId,
    required this.materialId,
    this.classroomId,
    this.supplementary = false,
    this.semanticLabel = 'A picture that supports this skill',
  });

  final String skillId;
  final String materialId;
  final String? classroomId;
  final bool supplementary;
  final String semanticLabel;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = skillImageProvider(
      skillId: skillId,
      materialId: materialId,
      classroomId: classroomId,
      supplementary: supplementary,
    );
    final image = ref.watch(provider);
    Widget unavailable() => Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SahlhaColors.tealSoft,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          const Icon(Icons.image_outlined, color: SahlhaColors.tealDark),
          const SizedBox(height: 8),
          const Text(
            "No picture is available right now.",
            textAlign: TextAlign.center,
          ),
          TextButton.icon(
            onPressed: () => ref.invalidate(provider),
            icon: const Icon(Icons.refresh),
            label: Text(
              "Try picture again",
              style: Theme.of(context).textTheme.labelLarge
                  ?.copyWith(color: SahlhaColors.tealDark),
            ),
          ),
        ],
      ),
    );
    return image.when(
      loading: () => const _ImageSkeleton(),
      error: (_, _) => unavailable(),
      data: (bytes) {
        if (bytes == null) return unavailable();
        return Semantics(
          image: true,
          label: semanticLabel,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: SahlhaColors.borderSubtle),
              boxShadow: SahlhaShadows.soft,
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: AspectRatio(
                aspectRatio: 16 / 10,
                child: Image.memory(
                  bytes,
                  fit: BoxFit.contain,
                  gaplessPlayback: true,
                  frameBuilder:
                      (context, child, frame, wasSynchronouslyLoaded) {
                        if (wasSynchronouslyLoaded || frame != null) {
                          return AnimatedOpacity(
                            opacity: frame == null ? 0 : 1,
                            duration: MediaQuery.disableAnimationsOf(context)
                                ? Duration.zero
                                : const Duration(milliseconds: 350),
                            curve: Curves.easeOut,
                            child: child,
                          );
                        }
                        return const _ImageSkeleton(borderless: true);
                      },
                  errorBuilder: (_, _, _) => unavailable(),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _ImageSkeleton extends StatelessWidget {
  const _ImageSkeleton({this.borderless = false});
  final bool borderless;
  @override
  Widget build(BuildContext context) {
    final radius = borderless ? BorderRadius.zero : BorderRadius.circular(20);
    return ClipRRect(
      borderRadius: radius,
      child: AspectRatio(
        aspectRatio: 16 / 10,
        child: Container(
          decoration: BoxDecoration(
            color: SahlhaColors.surfaceTealSoft,
            borderRadius: radius,
            border: borderless
                ? null
                : Border.all(color: SahlhaColors.borderSubtle),
          ),
          child: const Center(
            child: Icon(
              Icons.image_outlined,
              color: SahlhaColors.muted,
              size: 34,
            ),
          ),
        ),
      ),
    );
  }
}

/// Full lesson player using authenticated backend audio.
class ReadAloudButton extends ConsumerStatefulWidget {
  const ReadAloudButton({
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
  ConsumerState<ReadAloudButton> createState() => _ReadAloudButtonState();
}

class _ReadAloudButtonState extends ConsumerState<ReadAloudButton>
    with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;
  late final String _url = ref
      .read(studentRepositoryProvider)
      .skillAudioUrl(
        skillId: widget.skillId,
        materialId: widget.materialId,
        classroomId: widget.classroomId,
        supplementary: widget.supplementary,
      );

  /// Cached on every build: `ref` cannot be used in [dispose].
  AudioService? _audio;

  @override
  void dispose() {
    // Leaving the skill (or switching skills) stops this explanation so
    // two readings never overlap. The service is cached in a field because
    // `ref` is unsafe to use once the widget is unmounted.
    final audio = _audio;
    if (audio != null && audio.activeUrl == _url) {
      audio.stop();
    }
    super.dispose();
  }

  Future<void> _toggle(ReadAloudState state) async {
    final audio = ref.read(audioServiceProvider);
    HapticFeedback.selectionClick();
    if (state == ReadAloudState.playing) {
      await audio.pause();
      return;
    }
    if (state == ReadAloudState.paused && audio.activeUrl == _url) {
      await audio.resume();
      return;
    }
    final err = await audio.playUrl(_url);
    if (err != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err), duration: const Duration(seconds: 2)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    // Watching keeps the shared player alive while this skill is visible.
    final audio = ref.watch(audioServiceProvider);
    _audio = audio;
    return StreamBuilder<ReadAloudState>(
      stream: audio.stateStream,
      initialData: audio.activeUrl == _url ? audio.state : ReadAloudState.idle,
      builder: (context, snap) {
        var state = snap.data ?? ReadAloudState.idle;
        if (audio.activeUrl != _url) state = ReadAloudState.idle;
        final busy = state == ReadAloudState.loading;
        final ready = !busy && audio.activeUrl == _url;
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: SahlhaColors.tealSoft,
            borderRadius: BorderRadius.circular(22),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.headphones_rounded,
                    color: SahlhaColors.tealDark,
                  ),
                  const SizedBox(width: 8),
                  AudioCompanion(url: _url, size: 32),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Listen to this explanation',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              StreamBuilder<Duration?>(
                stream: audio.durationStream,
                initialData: audio.duration,
                builder: (context, durationSnapshot) => StreamBuilder<Duration>(
                  stream: audio.positionStream,
                  initialData: audio.position,
                  builder: (context, positionSnapshot) {
                    final total = ready
                        ? (durationSnapshot.data ?? Duration.zero)
                        : Duration.zero;
                    final position = ready
                        ? (positionSnapshot.data ?? Duration.zero)
                        : Duration.zero;
                    final max = total.inMilliseconds.toDouble();
                    return Column(
                      children: [
                        Slider(
                          semanticFormatterCallback: (value) =>
                              '${(value / 1000).round()} seconds',
                          min: 0,
                          max: max > 0 ? max : 1,
                          value: position.inMilliseconds.toDouble().clamp(
                            0,
                            max > 0 ? max : 1,
                          ),
                          onChanged: ready && max > 0
                              ? (value) => audio.seek(
                                  Duration(milliseconds: value.round()),
                                )
                              : null,
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [Text(_time(position)), Text(_time(total))],
                        ),
                      ],
                    );
                  },
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  FilledButton.icon(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(0, 48),
                    ),
                    onPressed: busy ? null : () => _toggle(state),
                    icon: Icon(
                      state == ReadAloudState.playing
                          ? Icons.pause_rounded
                          : Icons.play_arrow_rounded,
                    ),
                    label: Text(
                      switch (state) {
                        ReadAloudState.loading => 'Preparing audio...',
                        ReadAloudState.playing => 'Pause',
                        ReadAloudState.paused => 'Resume',
                        ReadAloudState.idle => 'Play lesson',
                      },
                      style: Theme.of(context).textTheme.labelLarge
                          ?.copyWith(color: Colors.white),
                    ),
                  ),
                  IconButton(
                    tooltip: busy ? 'Cancel audio' : 'Stop audio',
                    onPressed: audio.activeUrl == _url
                        ? () => audio.stop()
                        : null,
                    icon: const Icon(Icons.stop_rounded),
                  ),
                  IconButton(
                    tooltip: 'Replay from start',
                    onPressed: ready
                        ? () async {
                            await audio.seek(Duration.zero);
                            await audio.resume();
                          }
                        : null,
                    icon: const Icon(Icons.replay_rounded),
                  ),
                  PopupMenuButton<double>(
                    tooltip: 'Playback speed',
                    initialValue: audio.speed,
                    onSelected: (value) async {
                      await audio.setSpeed(value);
                      if (mounted) setState(() {});
                    },
                    itemBuilder: (_) => [
                      for (final speed in [0.75, 1.0, 1.25, 1.5, 2.0])
                        PopupMenuItem(value: speed, child: Text('${speed}x')),
                    ],
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text('${audio.speed}x'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  String _time(Duration value) =>
      '${value.inMinutes}:${(value.inSeconds % 60).toString().padLeft(2, '0')}';
}
