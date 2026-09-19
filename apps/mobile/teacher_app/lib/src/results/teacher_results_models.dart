class TeacherAssessment {
  const TeacherAssessment({
    required this.id,
    required this.sectionId,
    required this.subjectId,
    required this.subjectName,
    required this.code,
    required this.name,
    required this.maxMarks,
    this.scheduledOn,
  });

  final String id;
  final String sectionId;
  final String subjectId;
  final String subjectName;
  final String code;
  final String name;
  final int maxMarks;
  final String? scheduledOn;

  factory TeacherAssessment.fromJson(Map<String, dynamic> json) {
    return TeacherAssessment(
      id: json['id'] as String,
      sectionId: json['section_id'] as String,
      subjectId: json['subject_id'] as String,
      subjectName: json['subject_name'] as String,
      code: json['code'] as String,
      name: json['name'] as String,
      maxMarks: json['max_marks'] as int,
      scheduledOn: json['scheduled_on'] as String?,
    );
  }
}

class TeacherStudentMark {
  const TeacherStudentMark({
    required this.studentId,
    this.marks,
    this.markId,
    this.version,
  });

  final String studentId;
  final int? marks;
  final String? markId;
  final int? version;

  factory TeacherStudentMark.fromJson(Map<String, dynamic> json) {
    return TeacherStudentMark(
      studentId: json['student_id'] as String,
      marks: json['marks'] as int?,
      markId: json['mark_id'] as String?,
      version: json['version'] as int?,
    );
  }
}

class TeacherAssessmentMarks {
  const TeacherAssessmentMarks({
    required this.assessmentId,
    required this.maxMarks,
    required this.items,
  });

  final String assessmentId;
  final int maxMarks;
  final List<TeacherStudentMark> items;
}
