import 'package:flutter/foundation.dart';
import 'package:mobile_push/mobile_push.dart';

import '../auth/auth_models.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_classes_api.dart';
import 'teacher_dependencies.dart';

enum TeacherAppPhase { booting, signedOut, signedIn }

class TeacherAppController extends ChangeNotifier {
  TeacherAppController(this.deps);

  final TeacherDependencies deps;

  TeacherAppPhase phase = TeacherAppPhase.booting;
  List<TeacherClassAssignment> classes = const [];
  TeacherClassAssignment? selectedClass;
  String? errorMessage;
  bool loadingClasses = false;

  PushSetup get _pushSetup => PushSetup(
        getAuthToken: deps.tokenStore.readAccessToken,
        apiBaseUrl: deps.apiOrigin.toString(),
        appLabel: 'teacher',
      );

  Future<void> bootstrap() async {
    final session = await deps.authRepository.loadPersistedSession();
    if (session == null) {
      phase = TeacherAppPhase.signedOut;
      notifyListeners();
      return;
    }
    phase = TeacherAppPhase.signedIn;
    await _loadClasses();
    notifyListeners();
  }

  Future<void> login(String identifier, String password) async {
    errorMessage = null;
    try {
      await deps.authRepository.login(identifier: identifier, password: password);
      phase = TeacherAppPhase.signedIn;
      await _loadClasses();
      // Register the FCM token with the push endpoint now that we are
      // authenticated (registerPushToken never throws).
      final fcmToken = await currentFcmToken();
      if (fcmToken != null && fcmToken.isNotEmpty) {
        await registerPushToken(_pushSetup, fcmToken);
      }
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
    // Remove the push registration while we still hold the auth token
    // (unregisterPushToken never throws).
    await unregisterPushToken(_pushSetup);
    await deps.authRepository.logout();
    classes = const [];
    selectedClass = null;
    phase = TeacherAppPhase.signedOut;
    notifyListeners();
  }

  void selectClass(TeacherClassAssignment clazz) {
    selectedClass = clazz;
    notifyListeners();
  }

  Future<void> refreshClasses() => _loadClasses();

  Future<void> _loadClasses() async {
    loadingClasses = true;
    errorMessage = null;
    notifyListeners();
    try {
      final loaded = await deps.classesApi.fetchClasses();
      classes = loaded;
      if (loaded.isEmpty) {
        selectedClass = null;
      } else if (selectedClass == null ||
          !loaded.any((c) => c.sectionId == selectedClass!.sectionId)) {
        selectedClass = loaded.first;
      }
    } on TeacherClassesUnauthorized {
      await logout();
    } catch (_) {
      errorMessage = 'Could not load classes. Pull to retry.';
    } finally {
      loadingClasses = false;
      notifyListeners();
    }
  }
}
