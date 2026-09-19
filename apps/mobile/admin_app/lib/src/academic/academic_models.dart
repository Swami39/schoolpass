class AcademicYearItem {
  const AcademicYearItem({
    required this.id,
    required this.code,
    required this.name,
    required this.status,
  });

  final String id;
  final String code;
  final String name;
  final String status;

  factory AcademicYearItem.fromJson(Map<String, dynamic> json) => AcademicYearItem(
        id: json['id'] as String,
        code: json['code'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
      );
}

class SchoolClassItem {
  const SchoolClassItem({required this.id, required this.code, required this.name, required this.status});

  final String id;
  final String code;
  final String name;
  final String status;

  factory SchoolClassItem.fromJson(Map<String, dynamic> json) => SchoolClassItem(
        id: json['id'] as String,
        code: json['code'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
      );
}

class SectionItem {
  const SectionItem({required this.id, required this.classId, required this.name, required this.status});

  final String id;
  final String classId;
  final String name;
  final String status;

  factory SectionItem.fromJson(Map<String, dynamic> json) => SectionItem(
        id: json['id'] as String,
        classId: json['class_id'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
      );
}

class SubjectItem {
  const SubjectItem({required this.id, required this.code, required this.name, required this.status});

  final String id;
  final String code;
  final String name;
  final String status;

  factory SubjectItem.fromJson(Map<String, dynamic> json) => SubjectItem(
        id: json['id'] as String,
        code: json['code'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
      );
}

class TeacherAssignmentItem {
  const TeacherAssignmentItem({
    required this.id,
    required this.teacherUserId,
    required this.sectionId,
    required this.assignmentRole,
    required this.status,
  });

  final String id;
  final String teacherUserId;
  final String sectionId;
  final String assignmentRole;
  final String status;

  factory TeacherAssignmentItem.fromJson(Map<String, dynamic> json) => TeacherAssignmentItem(
        id: json['id'] as String,
        teacherUserId: json['teacher_user_id'] as String,
        sectionId: json['section_id'] as String,
        assignmentRole: json['assignment_role'] as String,
        status: json['status'] as String,
      );
}
