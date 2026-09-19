class TeacherStudent {
  const TeacherStudent({
    required this.id,
    required this.firstName,
    required this.lastName,
    required this.admissionNo,
    required this.status,
    this.middleName,
  });

  final String id;
  final String firstName;
  final String? middleName;
  final String lastName;
  final String admissionNo;
  final String status;

  String get displayName => [firstName, if (middleName != null) middleName, lastName].join(' ');

  factory TeacherStudent.fromJson(Map<String, dynamic> json) {
    return TeacherStudent(
      id: json['id'] as String,
      firstName: json['first_name'] as String,
      middleName: json['middle_name'] as String?,
      lastName: json['last_name'] as String,
      admissionNo: json['admission_no'] as String,
      status: json['status'] as String,
    );
  }
}
