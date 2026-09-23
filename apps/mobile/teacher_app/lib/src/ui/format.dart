/// Tiny date/time formatting helpers (no intl dependency needed).
const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _weekdaysFull = [
  'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
];
const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/// e.g. "Mon, 22 Sep"
String formatDay(DateTime d) =>
    '${_weekdays[d.weekday - 1]}, ${d.day} ${_months[d.month - 1]}';

/// e.g. "Mon, 22 Sep 2026"
String formatDayYear(DateTime d) => '${formatDay(d)} ${d.year}';

/// e.g. "Monday" for a 0-based (Mon=0) day index, matching the backend.
/// Out-of-range values wrap safely instead of crashing.
String weekdayIndexName(int dayOfWeek) => _weekdaysFull[dayOfWeek % 7];

/// e.g. "Mon" for a 0-based (Mon=0) day index, matching the backend.
String weekdayIndexShort(int dayOfWeek) => _weekdays[dayOfWeek % 7];

/// Formats a "HH:MM" or "HH:MM:SS" clock string as e.g. "8:04 AM".
String formatClock(String value) {
  final parts = value.split(':');
  if (parts.length < 2) return value;
  final hour = int.tryParse(parts[0]);
  final minute = int.tryParse(parts[1]);
  if (hour == null || minute == null) return value;
  final hour12 = hour % 12 == 0 ? 12 : hour % 12;
  final minuteStr = minute.toString().padLeft(2, '0');
  final ampm = hour < 12 ? 'AM' : 'PM';
  return '$hour12:$minuteStr $ampm';
}

/// e.g. "8:04 AM"
String formatTime(DateTime d) {
  final hour12 = d.hour % 12 == 0 ? 12 : d.hour % 12;
  final minute = d.minute.toString().padLeft(2, '0');
  final ampm = d.hour < 12 ? 'AM' : 'PM';
  return '$hour12:$minute $ampm';
}

/// e.g. "Just now", "5m ago", "3h ago", "2d ago", or a day string.
String relativeTime(DateTime d, {DateTime? now}) {
  final diff = (now ?? DateTime.now()).difference(d);
  if (diff.isNegative) return formatDay(d);
  if (diff.inMinutes < 1) return 'Just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
  return formatDay(d);
}

/// "Good morning/afternoon/evening" greeting for the home header.
String dayGreeting({DateTime? now}) {
  final hour = (now ?? DateTime.now()).hour;
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/// Capitalizes each word: "bus_boarding" -> "Bus Boarding".
String prettifyLabel(String raw) {
  return raw
      .replaceAll('_', ' ')
      .split(' ')
      .where((w) => w.isNotEmpty)
      .map((w) => w[0].toUpperCase() + w.substring(1).toLowerCase())
      .join(' ');
}
