import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

/// SchoolPass Bus Attendant theme.
///
/// Delegates to the shared CampusPass-inspired design system so the
/// attendant app matches the other SchoolPass apps (Material 3, paper
/// background, brand gradient accents, fixed status palette).
ThemeData buildAttendantTheme() {
  return SchoolPassTheme.build();
}
