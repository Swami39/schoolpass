import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'design_colors.dart';

/// Type system: Bricolage Grotesque for display/headlines (the CampusPass
/// prototype's display face), Inter for body/UI, JetBrains Mono for
/// credential values and timestamps that should read as data.
abstract final class DesignTypography {
  static TextTheme build(TextTheme base) {
    final body = GoogleFonts.interTextTheme(base);

    final themed = body.copyWith(
      displayLarge: GoogleFonts.bricolageGrotesque(
        textStyle: base.displayLarge,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.5,
      ),
      displayMedium: GoogleFonts.bricolageGrotesque(
        textStyle: base.displayMedium,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.5,
      ),
      displaySmall: GoogleFonts.bricolageGrotesque(
        textStyle: base.displaySmall,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.5,
      ),
      headlineLarge: GoogleFonts.bricolageGrotesque(
        textStyle: base.headlineLarge,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.5,
      ),
      headlineMedium: GoogleFonts.bricolageGrotesque(
        textStyle: base.headlineMedium,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.25,
      ),
      headlineSmall: GoogleFonts.bricolageGrotesque(
        textStyle: base.headlineSmall,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.25,
      ),
      titleLarge: GoogleFonts.bricolageGrotesque(
        textStyle: base.titleLarge,
        fontWeight: FontWeight.w700,
      ),
      titleMedium: GoogleFonts.inter(
        textStyle: base.titleMedium,
        fontWeight: FontWeight.w600,
      ),
    );

    return themed.apply(
      bodyColor: DesignColors.ink,
      displayColor: DesignColors.ink,
    );
  }

  /// Monospace style for card credential values and timestamps.
  static TextStyle mono({
    double size = 13,
    FontWeight weight = FontWeight.w500,
    Color? color,
    double spacing = 0.4,
  }) {
    return GoogleFonts.jetBrainsMono(
      fontSize: size,
      fontWeight: weight,
      color: color ?? DesignColors.ink,
      letterSpacing: spacing,
    );
  }

  /// Small, uppercased, tracked label — eyebrows and section headers.
  static TextStyle eyebrow({Color? color}) {
    return GoogleFonts.inter(
      fontSize: 11,
      fontWeight: FontWeight.w700,
      letterSpacing: 1.4,
      color: color ?? DesignColors.ink3,
    );
  }

  /// Display-face headline for hero cards (white on brand gradient).
  static TextStyle heroTitle({Color color = Colors.white, double size = 24}) {
    return GoogleFonts.bricolageGrotesque(
      fontSize: size,
      fontWeight: FontWeight.w800,
      letterSpacing: -0.5,
      color: color,
    );
  }
}
