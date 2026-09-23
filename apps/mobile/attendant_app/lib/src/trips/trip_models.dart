class AttendantTrip {
  AttendantTrip({
    required this.id,
    required this.status,
    required this.serviceDate,
    required this.shift,
    this.startedAt,
  });

  final String id;
  final String status;
  final String serviceDate;
  final String shift;
  final DateTime? startedAt;

  String get displayLabel => '$serviceDate · $shift · $status';

  bool get canStartBoarding => status == 'scheduled';

  bool get canScan => status == 'boarding' || status == 'in_progress';

  factory AttendantTrip.fromJson(Map<String, dynamic> json) {
    final started = json['started_at'];
    return AttendantTrip(
      id: json['id'] as String,
      status: json['status'] as String,
      serviceDate: json['service_date'] as String,
      shift: json['shift'] as String,
      startedAt: started == null ? null : DateTime.parse(started as String),
    );
  }
}
