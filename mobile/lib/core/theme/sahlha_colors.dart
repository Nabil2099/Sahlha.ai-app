import 'package:flutter/material.dart';

/// Sahlha design tokens — teal + cream + graphite + small warm accents.
/// Follows the Sahlha UI reference (NOT botanical, NOT Duolingo).
abstract final class SahlhaColors {
  static const Color cream = Color(0xFFFFF8EE);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceWarm = Color(0xFFFFF3E2);

  static const Color teal = Color(0xFF0E9388);
  static const Color tealDark = Color(0xFF0B6E64);
  static const Color tealSoft = Color(0xFFE3F4F1);
  static const Color tealFaint = Color(0xFFEFFAF8);

  static const Color ink = Color(0xFF22313F);
  static const Color muted = Color(0xFF64748B);
  static const Color line = Color(0xFFE9E1D3);

  static const Color sun = Color(0xFFFBBF24);
  static const Color sunSoft = Color(0xFFFEF3C7);
  static const Color coral = Color(0xFFF97066);

  static const Color success = Color(0xFF16A34A);
  static const Color successSoft = Color(0xFFDCFCE7);
  static const Color warning = Color(0xFFF59E0B);
  static const Color warningSoft = Color(0xFFFEF3C7);
  static const Color danger = Color(0xFFEF4444);
  static const Color dangerSoft = Color(0xFFFEE2E2);
  static const Color info = Color(0xFF0EA5E9);
  static const Color infoSoft = Color(0xFFE0F2FE);

  /// Calm status color for a student-facing mastery state.
  static Color mastery(String state) {
    return switch (state) {
      'mastered' => success,
      'developing' => teal,
      'needs_practice' => warning,
      _ => muted,
    };
  }

  static Color masterySoft(String state) {
    return switch (state) {
      'mastered' => successSoft,
      'developing' => tealSoft,
      'needs_practice' => warningSoft,
      _ => const Color(0xFFF1F5F9),
    };
  }
}
