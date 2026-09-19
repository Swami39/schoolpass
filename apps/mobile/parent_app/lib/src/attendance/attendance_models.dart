class AttendanceRecordItem {
  const AttendanceRecordItem({
    required this.id,
    required this.studentId,
    required this.attendanceDate,
    required this.status,
    required this.entryAt,
    required this.exitAt,
  });

  final String id;
  final String studentId;
  final String attendanceDate;
  final String status;
  final DateTime? entryAt;
  final DateTime? exitAt;

  factory AttendanceRecordItem.fromJson(Map<String, dynamic> json) {
    return AttendanceRecordItem(
      id: json['id'] as String,
      studentId: json['student_id'] as String,
      attendanceDate: json['attendance_date'] as String,
      status: json['status'] as String,
      entryAt: _parseDateTime(json['entry_at']),
      exitAt: _parseDateTime(json['exit_at']),
    );
  }

  static DateTime? _parseDateTime(Object? value) {
    if (value is! String || value.isEmpty) {
      return null;
    }
    return DateTime.tryParse(value);
  }
}
