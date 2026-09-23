import 'package:flutter/foundation.dart';
import 'package:mobile_push/mobile_push.dart';

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
  String? pendingMfaToken;

  PushSetup get _pushSetup => PushSetup(
        getAuthToken: deps.tokenStore.readAccessToken,
        apiBaseUrl: deps.apiOrigin.toString(),
        appLabel: 'admin',
      );

  Future<void> _registerPushTokenAfterLogin() async {
    // Register the FCM token with the push endpoint now that we are
    // authenticated (registerPushToken never throws).
    final fcmToken = await currentFcmToken();
    if (fcmToken != null && fcmToken.isNotEmpty) {
      await registerPushToken(_pushSetup, fcmToken);
    }
  }

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
    pendingMfaToken = null;
    try {
      await deps.authRepository.login(
        identifier: identifier,
        password: password,
        tenantId: deps.tenantId,
      );
      phase = AdminAppPhase.signedIn;
      section = AdminSection.dashboard;
      await _registerPushTokenAfterLogin();
    } on AuthNetworkFailure {
      errorMessage = 'Network error. Check your connection and try again.';
    } on AuthMfaRequired catch (e) {
      pendingMfaToken = e.mfaToken;
      errorMessage = null;
    } on AuthFailure catch (e) {
      errorMessage = e.message;
    }
    notifyListeners();
  }

  Future<void> submitMfa(String code) async {
    final token = pendingMfaToken;
    if (token == null || token.isEmpty) {
      errorMessage = 'No MFA challenge in progress.';
      notifyListeners();
      return;
    }
    errorMessage = null;
    try {
      await deps.authRepository.completeMfa(
        mfaToken: token,
        code: code.trim(),
        tenantId: deps.tenantId,
      );
      pendingMfaToken = null;
      phase = AdminAppPhase.signedIn;
      section = AdminSection.dashboard;
      await _registerPushTokenAfterLogin();
    } on AuthNetworkFailure {
      errorMessage = 'Network error. Check your connection and try again.';
    } on AuthFailure catch (e) {
      errorMessage = e.message;
    }
    notifyListeners();
  }

  void cancelMfa() {
    pendingMfaToken = null;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> logout() async {
    // Remove the push registration while we still hold the auth token
    // (unregisterPushToken never throws).
    await unregisterPushToken(_pushSetup);
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
    // SchoolProfileScreen loads the profile after the frame; do not notify again mid-build.
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
