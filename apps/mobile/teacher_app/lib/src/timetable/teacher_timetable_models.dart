class TeacherTimetablePeriod {
  const TeacherTimetablePeriod({
    required this.id,
    required this.sectionId,
    required this.className,
    required this.sectionName,
    required this.dayOfWeek,
    required this.periodNumber,
    required this.startsAt,
    required this.endsAt,
    required this.subjectId,
    required this.subjectName,
  });

  final String id;
  final String sectionId;
  final String className;
  final String sectionName;
  final int dayOfWeek;
  final int periodNumber;
  final String startsAt;
  final String endsAt;
  final String subjectId;
  final String subjectName;

  factory TeacherTimetablePeriod.fromJson(Map<String, dynamic> json) {
    return TeacherTimetablePeriod(
      id: json['id'] as String,
      sectionId: json['section_id'] as String,
      className: json['class_name'] as String,
      sectionName: json['section_name'] as String,
      dayOfWeek: json['day_of_week'] as int,
      periodNumber: json['period_number'] as int,
      startsAt: json['starts_at'] as String,
      endsAt: json['ends_at'] as String,
      subjectId: json['subject_id'] as String,
      subjectName: json['subject_name'] as String,
    );
  }
}
