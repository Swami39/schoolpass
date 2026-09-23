/// Tiny date/time formatting helpers (no intl dependency needed).
const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/// e.g. "Mon, 22 Sep"
String formatDay(DateTime d) =>
    '${_weekdays[d.weekday - 1]}, ${d.day} ${_months[d.month - 1]}';

/// e.g. "Mon, 22 Sep 2026"
String formatDayYear(DateTime d) => '${formatDay(d)} ${d.year}';

/// e.g. "8:04 AM"
String formatTime(DateTime d) {
  final hour12 = d.hour % 12 == 0 ? 12 : d.hour % 12;
  final minute = d.minute.toString().padLeft(2, '0');
  final ampm = d.hour < 12 ? 'AM' : 'PM';
  return '$hour12:$minute $ampm';
}

/// Parses an ISO date/time string; null when unparseable.
DateTime? tryParseDateTime(String raw) {
  try {
    return DateTime.parse(raw);
  } catch (_) {
    return null;
  }
}

/// Formats an ISO date string as "Mon, 22 Sep 2026"; falls back to raw.
String formatDateString(String raw) {
  final parsed = tryParseDateTime(raw);
  return parsed == null ? raw : formatDayYear(parsed);
}

/// Formats an ISO date/time string as "Mon, 22 Sep, 8:04 AM"; falls back to raw.
String formatDateTimeString(String raw) {
  final parsed = tryParseDateTime(raw);
  return parsed == null ? raw : '${formatDay(parsed)}, ${formatTime(parsed)}';
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

/// Capitalizes each word: "bus_attendant" -> "Bus Attendant".
String prettifyLabel(String raw) {
  return raw
      .replaceAll('_', ' ')
      .split(' ')
      .where((w) => w.isNotEmpty)
      .map((w) => w[0].toUpperCase() + w.substring(1).toLowerCase())
      .join(' ');
}
