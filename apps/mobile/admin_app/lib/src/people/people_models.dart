class StaffListItem {
  const StaffListItem({
    required this.id,
    required this.staffType,
    this.employeeCode,
    this.email,
  });

  final String id;
  final String staffType;
  final String? employeeCode;
  final String? email;

  factory StaffListItem.fromJson(Map<String, dynamic> json) => StaffListItem(
        id: json['id'] as String,
        staffType: json['staff_type'] as String,
        employeeCode: json['employee_code'] as String?,
        email: json['email'] as String?,
      );
}

class StaffDetail extends StaffListItem {
  const StaffDetail({
    required super.id,
    required super.staffType,
    required this.userId,
    super.employeeCode,
    super.email,
  });

  final String userId;

  factory StaffDetail.fromJson(Map<String, dynamic> json) => StaffDetail(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        staffType: json['staff_type'] as String,
        employeeCode: json['employee_code'] as String?,
        email: json['email'] as String?,
      );
}

class StudentDetail {
  const StudentDetail({
    required this.id,
    required this.admissionNo,
    required this.firstName,
    required this.lastName,
    required this.status,
    this.middleName,
    this.dateOfBirth,
  });

  final String id;
  final String admissionNo;
  final String firstName;
  final String? middleName;
  final String lastName;
  final String status;
  final String? dateOfBirth;

  String get displayName => '$firstName $lastName';

  factory StudentDetail.fromJson(Map<String, dynamic> json) => StudentDetail(
        id: json['id'] as String,
        admissionNo: json['admission_no'] as String,
        firstName: json['first_name'] as String,
        middleName: json['middle_name'] as String?,
        lastName: json['last_name'] as String,
        status: json['status'] as String,
        dateOfBirth: json['date_of_birth'] as String?,
      );
}

class GuardianDetail {
  const GuardianDetail({
    required this.id,
    required this.firstName,
    required this.lastName,
    required this.status,
    this.phoneE164,
    this.email,
    this.userId,
  });

  final String id;
  final String firstName;
  final String lastName;
  final String status;
  final String? phoneE164;
  final String? email;
  final String? userId;

  String get displayName => '$firstName $lastName';

  factory GuardianDetail.fromJson(Map<String, dynamic> json) => GuardianDetail(
        id: json['id'] as String,
        firstName: json['first_name'] as String,
        lastName: json['last_name'] as String,
        status: json['status'] as String,
        phoneE164: json['phone_e164'] as String?,
        email: json['email'] as String?,
        userId: json['user_id'] as String?,
      );
}

class EnrollmentDetail {
  const EnrollmentDetail({
    required this.id,
    required this.status,
    required this.sectionId,
    required this.classId,
    required this.academicYearId,
    required this.startsOn,
    this.endsOn,
  });

  final String id;
  final String status;
  final String sectionId;
  final String classId;
  final String academicYearId;
  final String startsOn;
  final String? endsOn;

  factory EnrollmentDetail.fromJson(Map<String, dynamic> json) => EnrollmentDetail(
        id: json['id'] as String,
        status: json['status'] as String,
        sectionId: json['section_id'] as String,
        classId: json['class_id'] as String,
        academicYearId: json['academic_year_id'] as String,
        startsOn: json['starts_on'] as String,
        endsOn: json['ends_on'] as String?,
      );
}

class StudentGuardianLink {
  const StudentGuardianLink({
    required this.id,
    required this.guardianId,
    required this.relationshipType,
    required this.isPrimaryContact,
    required this.status,
  });

  final String id;
  final String guardianId;
  final String relationshipType;
  final bool isPrimaryContact;
  final String status;

  factory StudentGuardianLink.fromJson(Map<String, dynamic> json) => StudentGuardianLink(
        id: json['id'] as String,
        guardianId: json['guardian_id'] as String,
        relationshipType: json['relationship_type'] as String,
        isPrimaryContact: json['is_primary_contact'] as bool? ?? false,
        status: json['status'] as String,
      );
}
