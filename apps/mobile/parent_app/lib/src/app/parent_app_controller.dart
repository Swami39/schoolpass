import 'package:flutter/foundation.dart';

import '../auth/auth_models.dart';
import '../children/child_models.dart';
import '../children/children_api.dart';
import 'parent_dependencies.dart';

enum ParentAppPhase { booting, signedOut, signedIn }

class ParentAppController extends ChangeNotifier {
  ParentAppController(this.deps);

  final ParentDependencies deps;

  ParentAppPhase phase = ParentAppPhase.booting;
  List<ParentChild> children = const [];
  ParentChild? selectedChild;
  String? errorMessage;
  bool loadingChildren = false;

  Future<void> bootstrap() async {
    final session = await deps.authRepository.loadPersistedSession();
    if (session == null) {
      phase = ParentAppPhase.signedOut;
      notifyListeners();
      return;
    }
    phase = ParentAppPhase.signedIn;
    await _loadChildren();
    notifyListeners();
  }

  Future<void> login(String identifier, String password) async {
    errorMessage = null;
    try {
      await deps.authRepository.login(identifier: identifier, password: password);
      phase = ParentAppPhase.signedIn;
      await _loadChildren();
      try {
        await deps.pushService.registerDeviceIfNeeded();
      } catch (_) {
        // Push registration is best-effort.
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
    deps.pushService.clearLocalRegistrationState();
    await deps.authRepository.logout();
    children = const [];
    selectedChild = null;
    phase = ParentAppPhase.signedOut;
    notifyListeners();
  }

  void selectChild(ParentChild child) {
    selectedChild = child;
    notifyListeners();
  }

  Future<void> refreshChildren() => _loadChildren();

  Future<void> _loadChildren() async {
    loadingChildren = true;
    errorMessage = null;
    notifyListeners();
    try {
      final loaded = await deps.childrenApi.fetchChildren();
      children = loaded;
      if (loaded.isEmpty) {
        selectedChild = null;
      } else if (selectedChild == null || !loaded.any((c) => c.id == selectedChild!.id)) {
        selectedChild = loaded.first;
      }
    } on ChildrenUnauthorized {
      await logout();
    } catch (_) {
      errorMessage = 'Could not load children. Pull to retry.';
    } finally {
      loadingChildren = false;
      notifyListeners();
    }
  }
}
