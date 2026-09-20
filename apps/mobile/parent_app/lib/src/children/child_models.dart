class ParentChild {
  const ParentChild({
    required this.id,
    required this.firstName,
    required this.middleName,
    required this.lastName,
    required this.admissionNo,
    required this.status,
  });

  final String id;
  final String firstName;
  final String? middleName;
  final String lastName;
  final String admissionNo;
  final String status;

  String get displayName {
    final parts = [firstName, if (middleName != null && middleName!.isNotEmpty) middleName, lastName]
        .whereType<String>()
        .where((p) => p.isNotEmpty);
    return parts.join(' ');
  }

  factory ParentChild.fromJson(Map<String, dynamic> json) {
    return ParentChild(
      id: (json['id'] ?? json['student_id']) as String,
      firstName: json['first_name'] as String,
      middleName: json['middle_name'] as String?,
      lastName: json['last_name'] as String,
      admissionNo: json['admission_no'] as String,
      status: json['status'] as String,
    );
  }
}
