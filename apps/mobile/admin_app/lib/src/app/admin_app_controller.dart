import 'package:flutter/foundation.dart';

import '../auth/auth_models.dart';
import '../school/admin_school_api.dart';
import '../school/school_profile_models.dart';
import 'admin_dependencies.dart';

enum AdminAppPhase { booting, signedOut, signedIn }

enum AdminSection {
  dashboard,
  school,
  academic,
  teachers,
  students,
  guardians,
  cards,
  transport,
  rfid,
  operations,
  audit,
}

class AdminAppController extends ChangeNotifier {
  AdminAppController(this.deps);

  final AdminDependencies deps;

  AdminAppPhase phase = AdminAppPhase.booting;
  AdminSection section = AdminSection.dashboard;
  SchoolProfile? schoolProfile;
  bool loadingProfile = false;
  bool savingProfile = false;
  String? errorMessage;
  String? successMessage;

  Future<void> bootstrap() async {
    final session = await deps.authRepository.loadPersistedSession();
    if (session == null) {
      phase = AdminAppPhase.signedOut;
      notifyListeners();
      return;
    }
    phase = AdminAppPhase.signedIn;
    notifyListeners();
  }

  Future<void> login(String identifier, String password) async {
    errorMessage = null;
    try {
      await deps.authRepository.login(identifier: identifier, password: password);
      phase = AdminAppPhase.signedIn;
      section = AdminSection.dashboard;
    } on AuthNetworkFailure {
      errorMessage = 'Network error. Check your connection and try again.';
    } on AuthMfaRequired {
      errorMessage = 'Multi-factor authentication is required for this account.';
    } on AuthFailure catch (e) {
      errorMessage = e.message;
    }
    notifyListeners();
  }

  Future<void> logout() async {
    await deps.authRepository.logout();
    schoolProfile = null;
    section = AdminSection.dashboard;
    phase = AdminAppPhase.signedOut;
    notifyListeners();
  }

  void selectSection(AdminSection value) {
    section = value;
    successMessage = null;
    errorMessage = null;
    notifyListeners();
    if (value == AdminSection.school && schoolProfile == null && !loadingProfile) {
      loadSchoolProfile();
    }
  }

  Future<void> loadSchoolProfile() async {
    loadingProfile = true;
    errorMessage = null;
    notifyListeners();
    try {
      schoolProfile = await deps.schoolApi.fetchProfile();
    } on AdminSchoolUnauthorized {
      await logout();
    } on AdminSchoolApiFailure catch (e) {
      errorMessage = e.message;
    } finally {
      loadingProfile = false;
      notifyListeners();
    }
  }

  Future<bool> saveSchoolProfile({
    required String legalName,
    String? displayName,
    required String timezone,
    required String country,
    String? contactEmail,
    String? contactPhone,
    String? addressLine1,
    String? city,
    String? state,
    String? postalCode,
  }) async {
    savingProfile = true;
    errorMessage = null;
    successMessage = null;
    notifyListeners();
    try {
      final body = SchoolProfile(
        id: schoolProfile?.id ?? '',
        legalName: legalName,
        displayName: displayName,
        slug: schoolProfile?.slug ?? '',
        status: schoolProfile?.status ?? 'active',
        timezone: timezone,
        country: country,
        contactEmail: contactEmail,
        contactPhone: contactPhone,
        addressLine1: addressLine1,
        city: city,
        state: state,
        postalCode: postalCode,
      ).toUpdateJson(
        legalName: legalName,
        displayName: displayName,
        timezone: timezone,
        country: country,
        contactEmail: contactEmail,
        contactPhone: contactPhone,
        addressLine1: addressLine1,
        city: city,
        state: state,
        postalCode: postalCode,
      );
      schoolProfile = await deps.schoolApi.updateProfile(body);
      successMessage = 'School profile saved';
      return true;
    } on AdminSchoolUnauthorized {
      await logout();
      return false;
    } on AdminSchoolApiFailure catch (e) {
      errorMessage = e.message;
      return false;
    } finally {
      savingProfile = false;
      notifyListeners();
    }
  }
}
