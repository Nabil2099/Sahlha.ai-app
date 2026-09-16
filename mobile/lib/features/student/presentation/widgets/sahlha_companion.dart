import 'dart:math' as math;

import 'package:flutter/material.dart';

enum CompanionMood { idle, listening, speaking, celebrating, retry }

/// Original vector character. A single slow cycle blinks and moves the antenna;
/// only speech moves the mouth. Reduced motion stops the ticker completely.
class SahlhaCompanion extends StatefulWidget {
  const SahlhaCompanion({
    super.key,
    this.size = 64,
    this.label,
    this.mood = CompanionMood.idle,
  });
  final double size;
  final String? label;
  final CompanionMood mood;
  @override
  State<SahlhaCompanion> createState() => _SahlhaCompanionState();
}

class _SahlhaCompanionState extends State<SahlhaCompanion>
    with SingleTickerProviderStateMixin {
  late final _motion = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  );
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context) ||
        MediaQuery.accessibleNavigationOf(context)) {
      _motion.stop();
      _motion.value = 0;
    } else if (!_motion.isAnimating) {
      _motion.repeat();
    }
  }

  @override
  void dispose() {
    _motion.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final face = AnimatedBuilder(
      animation: _motion,
      builder: (_, _) => SizedBox.square(
        dimension: widget.size,
        child: CustomPaint(
          painter: _CompanionPainter(_motion.value, widget.mood),
        ),
      ),
    );
    return widget.label == null
        ? ExcludeSemantics(child: face)
        : Semantics(image: true, label: widget.label, child: face);
  }
}

class _CompanionPainter extends CustomPainter {
  const _CompanionPainter(this.phase, this.mood);
  final double phase;
  final CompanionMood mood;
  @override
  void paint(Canvas c, Size size) {
    c.save();
    c.scale(size.width / 100, size.height / 100);
    final wave = math.sin(phase * math.pi * 2);
    c.translate(50, 55);
    c.rotate(wave * .012);
    c.translate(-50, -55);
    final teal = Paint()..color = const Color(0xFF149C96);
    final antenna = Path()
      ..moveTo(60, 24)
      ..quadraticBezierTo(66 + wave, 3, 81, 15 + wave);
    c.drawPath(
      antenna,
      Paint()
        ..color = const Color(0xFF078B86)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4
        ..strokeCap = StrokeCap.round,
    );
    c.drawOval(
      const Rect.fromLTWH(9, 23, 81, 70),
      Paint()
        ..shader = const LinearGradient(
          colors: [Color(0xFF6CCFC4), Color(0xFF008F8A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ).createShader(const Rect.fromLTWH(9, 23, 81, 70)),
    );
    c.drawOval(
      const Rect.fromLTWH(16, 30, 65, 56),
      Paint()..color = const Color(0xFF94DFD3),
    );
    c.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(24, 40, 51, 35),
        const Radius.circular(18),
      ),
      Paint()..color = const Color(0xFF193B4A),
    );
    final blink = phase > .91 && phase < .94;
    for (final x in [38.0, 61.0]) {
      c.drawOval(
        Rect.fromCenter(
          center: Offset(x, 53),
          width: 9,
          height: blink ? 2 : (mood == CompanionMood.celebrating ? 6 : 10),
        ),
        Paint()..color = Colors.white,
      );
      if (!blink) {
        c.drawCircle(
          Offset(x + 1, 51),
          1.7,
          Paint()..color = const Color(0xFFB6F1ED),
        );
      }
    }
    final opening = mood == CompanionMood.speaking
        ? 2 + 5 * math.sin(phase * math.pi * 48).abs()
        : 2.0;
    c.drawOval(
      Rect.fromCenter(
        center: const Offset(49, 66),
        width: mood == CompanionMood.retry ? 7 : 10,
        height: opening,
      ),
      Paint()..color = const Color(0xFFD7F9F2),
    );
    c.drawOval(const Rect.fromLTWH(13, 69, 17, 16), teal);
    c.drawOval(const Rect.fromLTWH(68, 71, 17, 15), teal);
    if (mood == CompanionMood.celebrating) {
      for (final p in [const Offset(9, 15), const Offset(90, 35)]) {
        c.drawPath(
          Path()
            ..moveTo(p.dx, p.dy - 5)
            ..lineTo(p.dx + 2, p.dy - 1)
            ..lineTo(p.dx + 5, p.dy)
            ..lineTo(p.dx + 2, p.dy + 2)
            ..lineTo(p.dx, p.dy + 6)
            ..lineTo(p.dx - 2, p.dy + 2)
            ..lineTo(p.dx - 5, p.dy)
            ..lineTo(p.dx - 2, p.dy - 1)
            ..close(),
          Paint()..color = const Color(0xFFFFBF33),
        );
      }
    }
    if (mood == CompanionMood.listening) {
      c.drawArc(
        const Rect.fromLTWH(18, 34, 63, 48),
        math.pi,
        math.pi,
        false,
        Paint()
          ..color = const Color(0xFF087D78)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3,
      );
    }
    c.restore();
  }

  @override
  bool shouldRepaint(_CompanionPainter old) =>
      old.phase != phase || old.mood != mood;
}
