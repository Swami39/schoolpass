class ParentNotification {
  const ParentNotification({
    required this.id,
    required this.notificationType,
    required this.title,
    required this.body,
    required this.read,
    required this.createdAt,
    this.studentId,
  });

  final String id;
  final String notificationType;
  final String title;
  final String body;
  final bool read;
  final DateTime createdAt;
  final String? studentId;

  factory ParentNotification.fromJson(Map<String, dynamic> json) {
    return ParentNotification(
      id: json['id'] as String,
      notificationType: json['notification_type'] as String,
      title: json['title'] as String,
      body: json['body'] as String,
      read: json['read'] as bool,
      createdAt: DateTime.parse(json['created_at'] as String),
      studentId: json['student_id'] as String?,
    );
  }
}
