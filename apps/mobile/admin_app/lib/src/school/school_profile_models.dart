class SchoolProfile {
  const SchoolProfile({
    required this.id,
    required this.legalName,
    this.displayName,
    required this.slug,
    required this.status,
    required this.timezone,
    required this.country,
    this.contactEmail,
    this.contactPhone,
    this.addressLine1,
    this.city,
    this.state,
    this.postalCode,
    this.logoFileId,
  });

  final String id;
  final String legalName;
  final String? displayName;
  final String slug;
  final String status;
  final String timezone;
  final String country;
  final String? contactEmail;
  final String? contactPhone;
  final String? addressLine1;
  final String? city;
  final String? state;
  final String? postalCode;
  final String? logoFileId;

  String get displayLabel => (displayName != null && displayName!.isNotEmpty) ? displayName! : legalName;

  factory SchoolProfile.fromJson(Map<String, dynamic> json) {
    return SchoolProfile(
      id: json['id'] as String,
      legalName: json['legal_name'] as String,
      displayName: json['display_name'] as String?,
      slug: json['slug'] as String,
      status: json['status'] as String,
      timezone: json['timezone'] as String,
      country: json['country'] as String,
      contactEmail: json['contact_email'] as String?,
      contactPhone: json['contact_phone'] as String?,
      addressLine1: json['address_line1'] as String?,
      city: json['city'] as String?,
      state: json['state'] as String?,
      postalCode: json['postal_code'] as String?,
      logoFileId: json['logo_file_id'] as String?,
    );
  }

  Map<String, dynamic> toUpdateJson({
    String? legalName,
    String? displayName,
    String? timezone,
    String? country,
    String? contactEmail,
    String? contactPhone,
    String? addressLine1,
    String? city,
    String? state,
    String? postalCode,
  }) {
    final map = <String, dynamic>{};
    if (legalName != null) map['legal_name'] = legalName;
    if (displayName != null) map['display_name'] = displayName;
    if (timezone != null) map['timezone'] = timezone;
    if (country != null) map['country'] = country;
    if (contactEmail != null) map['contact_email'] = contactEmail;
    if (contactPhone != null) map['contact_phone'] = contactPhone;
    if (addressLine1 != null) map['address_line1'] = addressLine1;
    if (city != null) map['city'] = city;
    if (state != null) map['state'] = state;
    if (postalCode != null) map['postal_code'] = postalCode;
    return map;
  }
}
