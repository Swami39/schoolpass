import 'package:flutter/foundation.dart';
import 'package:mobile_push/mobile_push.dart';

import '../api/attendant_errors.dart';
import '../auth/auth_models.dart';
import '../trips/trip_models.dart';
import 'attendant_dependencies.dart';

enum AttendantAppPhase { booting, signedOut, signedIn }

class AttendantAppController extends ChangeNotifier {
  AttendantAppController(this.deps);

  final AttendantDependencies deps;

  AttendantAppPhase phase = AttendantAppPhase.booting;
  List<AttendantTrip> trips = const [];
  AttendantTrip? selectedTrip;
  String? errorMessage;
  bool loadingTrips = false;

  PushSetup get _pushSetup => PushSetup(
        getAuthToken: deps.tokenStore.readAccessToken,
        apiBaseUrl: deps.apiOrigin.toString(),
        appLabel: 'attendant',
      );

  Future<void> bootstrap() async {
    final session = await deps.authRepository.loadPersistedSession();
    if (session == null) {
      phase = AttendantAppPhase.signedOut;
      notifyListeners();
      return;
    }
    phase = AttendantAppPhase.signedIn;
    await _loadTrips();
    notifyListeners();
  }

  Future<void> login(String identifier, String password) async {
    errorMessage = null;
    try {
      await deps.authRepository.login(identifier: identifier, password: password);
      phase = AttendantAppPhase.signedIn;
      await _loadTrips();
      // Register the FCM token with the push endpoint now that we are
      // authenticated (registerPushToken never throws).
      final fcmToken = await currentFcmToken();
      if (fcmToken != null && fcmToken.isNotEmpty) {
        await registerPushToken(_pushSetup, fcmToken);
      }
    } on AuthNetworkFailure {
      errorMessage = 'Network error. Check Wi‑Fi and that the Mac API is reachable.';
    } on AuthMfaRequired {
      errorMessage = 'MFA is not supported on the attendant app.';
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
    trips = const [];
    selectedTrip = null;
    phase = AttendantAppPhase.signedOut;
    notifyListeners();
  }

  Future<void> refreshTrips() => _loadTrips();

  Future<AttendantTrip?> startBoarding(AttendantTrip trip) async {
    errorMessage = null;
    notifyListeners();
    try {
      final updated = await deps.tripsApi.startTripBoarding(trip.id);
      await _loadTrips();
      selectedTrip = updated;
      notifyListeners();
      return updated;
    } on AttendantUnauthorized {
      await logout();
    } catch (_) {
      errorMessage = 'Could not start boarding for this trip.';
      notifyListeners();
    }
    return null;
  }

  void selectTrip(AttendantTrip trip) {
    selectedTrip = trip;
    notifyListeners();
  }

  Future<void> _loadTrips() async {
    loadingTrips = true;
    errorMessage = null;
    notifyListeners();
    try {
      final loaded = await deps.tripsApi.fetchMyTripsToday();
      trips = loaded;
      if (loaded.isEmpty) {
        selectedTrip = null;
      } else if (selectedTrip == null || !loaded.any((t) => t.id == selectedTrip!.id)) {
        selectedTrip = loaded.first;
      } else {
        selectedTrip = loaded.firstWhere((t) => t.id == selectedTrip!.id);
      }
    } on AttendantUnauthorized {
      await logout();
    } catch (_) {
      errorMessage = 'Could not load today’s trips.';
    } finally {
      loadingTrips = false;
      notifyListeners();
    }
  }
}
