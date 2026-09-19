class TeacherAttendanceRecord {
  const TeacherAttendanceRecord({
    required this.id,
    required this.studentId,
    required this.attendanceDate,
    required this.status,
    required this.source,
    this.entryAt,
    this.exitAt,
  });

  final String id;
  final String studentId;
  final String attendanceDate;
  final String status;
  final String source;
  final DateTime? entryAt;
  final DateTime? exitAt;

  factory TeacherAttendanceRecord.fromJson(Map<String, dynamic> json) {
    return TeacherAttendanceRecord(
      id: json['id'] as String,
      studentId: json['student_id'] as String,
      attendanceDate: json['attendance_date'] as String,
      status: json['status'] as String,
      source: json['source'] as String,
      entryAt: json['entry_at'] == null ? null : DateTime.parse(json['entry_at'] as String),
      exitAt: json['exit_at'] == null ? null : DateTime.parse(json['exit_at'] as String),
    );
  }
}
