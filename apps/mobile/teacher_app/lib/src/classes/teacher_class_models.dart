class TeacherClassAssignment {
  const TeacherClassAssignment({
    required this.sectionId,
    required this.classId,
    required this.className,
    required this.sectionName,
    required this.studentCount,
    required this.todayPresentCount,
    required this.todayAbsentCount,
    this.subjectName,
  });

  final String sectionId;
  final String classId;
  final String className;
  final String sectionName;
  final String? subjectName;
  final int studentCount;
  final int todayPresentCount;
  final int todayAbsentCount;

  String get displayLabel => '$className-$sectionName';

  factory TeacherClassAssignment.fromJson(Map<String, dynamic> json) {
    return TeacherClassAssignment(
      sectionId: json['section_id'] as String,
      classId: json['class_id'] as String,
      className: json['class_name'] as String,
      sectionName: json['section_name'] as String,
      subjectName: json['subject_name'] as String?,
      studentCount: json['student_count'] as int,
      todayPresentCount: json['today_present_count'] as int,
      todayAbsentCount: json['today_absent_count'] as int,
    );
  }
}
