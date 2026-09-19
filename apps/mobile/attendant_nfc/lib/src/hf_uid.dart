/// Matches server `normalize_hf_uid`: strip whitespace; empty → null.
String? normalizeHfUid(String? value) {
  if (value == null) {
    return null;
  }
  final cleaned = value.trim();
  return cleaned.isEmpty ? null : cleaned;
}
