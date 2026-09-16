import 'subject_visuals.dart';
import 'audio_companion.dart';
import 'loop_trace.dart';

import 'dart:async';

import 'package:flutter/material.dart';

import '../../domain/skill_models.dart';
import '../journey_presentation.dart';
import 'sahlha_companion.dart';

/// Only source-backed content is displayed. Unsupported code is a reading
/// walkthrough, never presented as executed code or used to score an answer.
class LearningPlayground extends StatefulWidget {
  const LearningPlayground({
    super.key,
    required this.skill,
    this.subject = '',
    this.audioUrl,
  });
  final SkillBundle skill;
  final String subject;
  final String? audioUrl;
  @override
  State<LearningPlayground> createState() => _LearningPlaygroundState();
}

class _LearningPlaygroundState extends State<LearningPlayground> {
  int _step = 0;
  Timer? _timer;
  bool _running = false;
  final List<int> _words = [];
  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  void didUpdateWidget(LearningPlayground oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.skill != widget.skill) {
      _timer?.cancel();
      _running = false;
      _step = 0;
      _words.clear();
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if ((MediaQuery.disableAnimationsOf(context) ||
        MediaQuery.accessibleNavigationOf(context))) {
      _timer?.cancel();
      _running = false;
    }
  }

  void _advance(int count) => setState(() => _step = (_step + 1) % count);
  @override
  Widget build(BuildContext context) {
    final source = widget.skill.explanation.isEmpty
        ? widget.skill.description
        : widget.skill.explanation;
    final evidence =
        '${widget.subject} ${widget.skill.name} ${widget.skill.description}'
            .toLowerCase();
    final code = RegExp(r'```[^\n]*\n([\s\S]*?)```')
        .firstMatch(source)
        ?.group(1)
        ?.trim();
    final ideas = widget.skill.keyConcepts.isNotEmpty
        ? widget.skill.keyConcepts
        : lessonSections(source);
    var content = ideas.isEmpty ? [widget.skill.name] : ideas;
    final language = RegExp(
      r'language|english|arabic|grammar|sentence|لغة|عربي',
    ).hasMatch(evidence);
    final math = RegExp(r'math|number|equation|algebra|رياض|حساب')
        .hasMatch(evidence);
    final history = RegExp(r'history|histor|timeline|تاريخ').hasMatch(evidence);
    final geography = RegExp(r'geograph|location|latitude|جغراف')
        .hasMatch(evidence);
    if (history) {
      final events = source
          .split(RegExp(r'\n+'))
          .where((line) => RegExp(r'\b\d{3,4}\b').hasMatch(line))
          .toList();
      if (events.isNotEmpty) content = events;
    }
    if (math) {
      final equations = source
          .split(RegExp(r'\n+'))
          .where((line) => line.contains('='))
          .toList();
      if (equations.isNotEmpty) content = equations;
    }
    final programming =
        code != null ||
        RegExp(r'program|python|code|loop|برمج').hasMatch(evidence);
    final trace = code == null ? null : LoopTrace.fromCode(code);
    final frame = trace == null
        ? null
        : trace.frames[_step % trace.frames.length];
    final lines = code?.split('\n') ?? content;
    final index =
        frame?.line ?? _step % (programming ? lines.length : content.length);
    final count = trace?.frames.length ?? lines.length;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: programming
              ? [const Color(0xFFCFE6FF), const Color(0xFFAED6FF)]
              : [const Color(0xFFFDF2D9), const Color(0xFFF8F4E9)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  programming
                      ? 'See how it works'
                      : history
                      ? 'Explore the timeline'
                      : geography
                      ? 'Explore locations'
                      : language
                      ? 'Build the sentence'
                      : math
                      ? 'Explore the steps'
                      : 'Explore the idea',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              if (widget.audioUrl != null)
                AudioCompanion(url: widget.audioUrl!, size: 58)
              else
                const SahlhaCompanion(size: 58),
            ],
          ),
          const SizedBox(height: 12),
          if (programming) ...[
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFF203B50),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.circle, size: 7, color: Color(0xFF7BD4C6)),
                      SizedBox(width: 5),
                      Icon(Icons.circle, size: 7, color: Color(0xFFFFDB80)),
                      SizedBox(width: 5),
                      Icon(Icons.circle, size: 7, color: Color(0xFF7BD4C6)),
                    ],
                  ),
                  const SizedBox(height: 10),
                  for (var i = 0; i < lines.length; i++)
                    if ((i - index).abs() <= 2)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          vertical: 5,
                          horizontal: 6,
                        ),
                        color: i == index
                            ? const Color(0xFF365B70)
                            : Colors.transparent,
                        child: Text(
                          lines[i],
                          style: TextStyle(
                            fontFamily: code != null ? 'monospace' : null,
                            height: 1.6,
                            color: i == index
                                ? const Color(0xFFFFE28D)
                                : Colors.white,
                          ),
                        ),
                      ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            if (trace != null)
              const Wrap(
                alignment: WrapAlignment.center,
                spacing: 8,
                runSpacing: 8,
                children: [
                  Text('Condition', style: TextStyle(fontSize: 12)),
                  Text('True: repeat', style: TextStyle(fontSize: 12)),
                  Text('False: exit', style: TextStyle(fontSize: 12)),
                ],
              ),
            Text('Step ${_step + 1} of $count', textAlign: TextAlign.center),
            if (frame != null) ...[
              const SizedBox(height: 8),
              Text(
                '${trace!.variable} = ${frame.value}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(
                'Output: ${frame.output.join(" ")}',
                style: const TextStyle(fontFamily: 'monospace'),
              ),
              Semantics(liveRegion: true, child: Text(frame.message)),
            ],
            TextButton.icon(
              onPressed: () {
                if (_running) {
                  _timer?.cancel();
                  setState(() => _running = false);
                  return;
                }
                if ((MediaQuery.disableAnimationsOf(context) ||
                    MediaQuery.accessibleNavigationOf(context))) {
                  _advance(count);
                  return;
                }
                setState(() {
                  if (_step >= count - 1) _step = 0;
                  _running = true;
                });
                _timer = Timer.periodic(const Duration(milliseconds: 1400), (
                  timer,
                ) {
                  if (!mounted) {
                    timer.cancel();
                    return;
                  }
                  if (_step >= count - 1) {
                    timer.cancel();
                    setState(() => _running = false);
                  } else {
                    _advance(count);
                  }
                });
              },
              icon: Icon(_running ? Icons.pause : Icons.play_arrow),
              label: Text(
                _running
                    ? 'Pause'
                    : trace == null
                    ? 'Run walkthrough'
                    : 'Run',
              ),
            ),
          ] else if (language) ...[
            Builder(
              builder: (context) {
                final sentence = source.split(RegExp(r'(?<=[.!?])\s+')).first;
                final words = sentence.split(RegExp(r'\s+')).take(24).toList();
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      sentence,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 6,
                      children: [
                        for (var i = words.length - 1; i >= 0; i--)
                          FilterChip(
                            label: Text(words[i]),
                            selected: _words.contains(i),
                            onSelected: (selected) => setState(() {
                              if (selected) {
                                _words.add(i);
                              } else {
                                _words.remove(i);
                              }
                            }),
                          ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _words.map((i) => words[i]).join(' '),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    TextButton(
                      onPressed: () => setState(_words.clear),
                      child: const Text('Try another arrangement'),
                    ),
                  ],
                );
              },
            ),
          ] else ...[
            if (math) ...[
              _NumberLine(source: source),
              CoordinatePlot(source: source),
            ],
            if (geography) CoordinatePlot(source: source, geographic: true),
            if (history)
              LessonTimeline(
                events: content,
                selected: index,
                onSelect: (i) => setState(() => _step = i),
              )
            else if (!math && !geography)
              ConceptDiagram(
                title: studentTitle(widget.skill.name),
                labels: content,
                selected: index,
                onSelect: (i) => setState(() => _step = i),
              ),
            if (math || geography)
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (var i = 0; i < content.length; i++)
                    ChoiceChip(
                      selected: index == i,
                      label: Text(history ? '${i + 1} →' : '${i + 1}'),
                      onSelected: (_) => setState(() => _step = i),
                    ),
                ],
              ),
            const SizedBox(height: 14),
            if (!history)
              Semantics(
                liveRegion: true,
                child: Text(
                  cleanStudentText(content[index]),
                  style: Theme.of(context).textTheme.bodyLarge
                      ?.copyWith(height: 1.6),
                ),
              ),
            if (content.length > 1)
              TextButton.icon(
                onPressed: () => _advance(content.length),
                icon: const Icon(Icons.arrow_forward),
                label: Text(history ? 'Next event' : 'Reveal next step'),
              ),
          ],
        ],
      ),
    );
  }
}

class _NumberLine extends StatefulWidget {
  const _NumberLine({required this.source});
  final String source;
  @override
  State<_NumberLine> createState() => _NumberLineState();
}

class _NumberLineState extends State<_NumberLine> {
  double? _value;
  @override
  Widget build(BuildContext context) {
    final values =
        RegExp(r'(?<!\w)-?\d+(?:\.\d+)?')
            .allMatches(widget.source)
            .map((m) => double.tryParse(m.group(0)!))
            .whereType<double>()
            .where((v) => v.isFinite)
            .toSet()
            .toList()
          ..sort();
    if (values.length < 2) return const SizedBox.shrink();
    final lo = values.first, hi = values.last;
    return Column(
      children: [
        Text('Number line: ${(_value ?? lo).toStringAsFixed(1)}'),
        Slider(
          min: lo,
          max: hi,
          value: (_value ?? lo).clamp(lo, hi),
          onChanged: (v) => setState(() => _value = v),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [Text('$lo'), Text('$hi')],
        ),
        const SizedBox(height: 12),
      ],
    );
  }
}
