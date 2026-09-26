import 'package:flutter/material.dart';

/// Design tokens shared by all SchoolPass apps, adapted from the CampusPass
/// prototype: deep indigo-plum ink on cool paper, a purple brand gradient,
/// and a fixed meaning-carrying status palette.
abstract final class DesignColors {
  /// Brand purple (gradient start).
  static const Color brand = Color(0xFF6D4AFF);

  /// Brand purple (gradient end).
  static const Color brand2 = Color(0xFF8B6BFF);

  /// Dark brand ink for text on brand tints.
  static const Color brandInk = Color(0xFF4A2FD6);

  /// Soft brand tint for selected / highlighted surfaces.
  static const Color brandSoft = Color(0xFFEFEBFF);

  /// Primary text.
  static const Color ink = Color(0xFF201A3B);

  /// Secondary text.
  static const Color ink2 = Color(0xFF565073);

  /// Captions and metadata.
  static const Color ink3 = Color(0xFF8C87A6);

  /// App background.
  static const Color paper = Color(0xFFF3F4FA);

  /// Raised surfaces (cards, sheets).
  static const Color surface = Colors.white;

  /// Hairline borders and dividers.
  static const Color line = Color(0xFFECEBF4);

  /// Stronger hairline (timeline rails, etc.).
  static const Color line2 = Color(0xFFE1DFEE);

  // Status palette — meaning-carrying, fixed across schools.
  static const Color present = Color(0xFF0FB07C);
  static const Color late = Color(0xFFEC9A0C);
  static const Color absent = Color(0xFFEF5468);
  static const Color bus = Color(0xFF1FA8DC);

  /// Default brand gradient used by hero cards and primary buttons.
  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [brand, brand2],
  );
}

/// The finite set of meanings a status colour can express. Screens ask for a
/// *meaning* and the theme decides how to paint it.
enum StatusKind { present, late, absent, bus, neutral }

/// Theme extension carrying the status palette so widgets read status colours
/// from the theme (`context.status.of(kind)`) instead of hard-coding them.
@immutable
class StatusColors extends ThemeExtension<StatusColors> {
  const StatusColors({
    required this.present,
    required this.late,
    required this.absent,
    required this.bus,
    required this.neutral,
  });

  final Color present;
  final Color late;
  final Color absent;
  final Color bus;
  final Color neutral;

  static const StatusColors standard = StatusColors(
    present: DesignColors.present,
    late: DesignColors.late,
    absent: DesignColors.absent,
    bus: DesignColors.bus,
    neutral: DesignColors.ink3,
  );

  /// The solid colour for a meaning.
  Color of(StatusKind kind) => switch (kind) {
        StatusKind.present => present,
        StatusKind.late => late,
        StatusKind.absent => absent,
        StatusKind.bus => bus,
        StatusKind.neutral => neutral,
      };

  /// A soft tinted background for the same meaning (pills, chips).
  Color softOf(StatusKind kind) => of(kind).withValues(alpha: 0.12);

  @override
  StatusColors copyWith({
    Color? present,
    Color? late,
    Color? absent,
    Color? bus,
    Color? neutral,
  }) {
    return StatusColors(
      present: present ?? this.present,
      late: late ?? this.late,
      absent: absent ?? this.absent,
      bus: bus ?? this.bus,
      neutral: neutral ?? this.neutral,
    );
  }

  @override
  StatusColors lerp(ThemeExtension<StatusColors>? other, double t) {
    if (other is! StatusColors) return this;
    return StatusColors(
      present: Color.lerp(present, other.present, t)!,
      late: Color.lerp(late, other.late, t)!,
      absent: Color.lerp(absent, other.absent, t)!,
      bus: Color.lerp(bus, other.bus, t)!,
      neutral: Color.lerp(neutral, other.neutral, t)!,
    );
  }
}

/// Ergonomic access: `context.status.of(StatusKind.present)`.
extension StatusColorsX on BuildContext {
  StatusColors get status =>
      Theme.of(this).extension<StatusColors>() ?? StatusColors.standard;
}
