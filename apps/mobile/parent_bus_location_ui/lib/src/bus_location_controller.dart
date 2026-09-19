import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:parent_transport/parent_transport.dart';

import 'freshness_policy.dart';
import 'repository.dart';
import 'view_state.dart';

typedef ParentBusLocationClock = DateTime Function();

/// Feature-local controller: fetch, manual refresh, and foreground polling.
class ParentBusLocationController extends ChangeNotifier {
  ParentBusLocationController({
    required ParentBusLocationRepository repository,
    required String studentId,
    this.pollInterval = const Duration(seconds: 20),
    this.freshnessPolicy = const BusLocationFreshnessPolicy(),
    ParentBusLocationClock? clock,
    this.onAuthFailure,
  })  : _repository = repository,
        _studentId = studentId,
        _clock = clock ?? DateTime.now;

  final ParentBusLocationRepository _repository;
  final String _studentId;
  final Duration pollInterval;
  final BusLocationFreshnessPolicy freshnessPolicy;
  final ParentBusLocationClock _clock;
  final void Function(int statusCode)? onAuthFailure;

  Timer? _pollTimer;
  bool _disposed = false;
  bool _requestInFlight = false;
  bool _pollingActive = false;

  ParentBusLocationViewState _state = ParentBusLocationViewState.loading();
  ParentBusLocationViewState get state => _state;

  int fetchCallCount = 0;
  String? lastFetchedStudentId;

  void startForegroundPolling() {
    if (_disposed || _pollingActive) {
      return;
    }
    _pollingActive = true;
    unawaited(refresh());
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(pollInterval, (_) {
      unawaited(refresh(isBackground: true));
    });
  }

  void stopForegroundPolling() {
    _pollingActive = false;
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> refresh({bool manual = false, bool isBackground = false}) async {
    if (_disposed || _requestInFlight) {
      return;
    }
    _requestInFlight = true;
    final showRefresh = manual || (_state.kind != ParentBusLocationUiKind.loading);
    _setState(
      _state.kind == ParentBusLocationUiKind.loading && !manual
          ? ParentBusLocationViewState.loading()
          : ParentBusLocationViewState(
              kind: _state.kind,
              display: _state.display,
              message: _state.message,
              isRefreshing: showRefresh,
            ),
    );

    try {
      lastFetchedStudentId = _studentId;
      fetchCallCount += 1;
      final location = await _repository.fetchChildBusLocation(studentId: _studentId);
      _setState(
        ParentBusLocationViewState.fromLocation(
          location,
          freshnessPolicy: freshnessPolicy,
          now: _clock(),
          isRefreshing: false,
        ),
      );
    } on ParentBusLocationNotFoundFailure {
      _setState(
        ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.notFound,
          message: ParentBusLocationCopy.notFound,
        ),
      );
    } on ParentBusLocationAuthFailure catch (e) {
      onAuthFailure?.call(e.statusCode);
      _setState(
        ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.authError,
          message: ParentBusLocationCopy.temporaryError,
        ),
      );
    } on ParentBusLocationNetworkFailure {
      _setState(
        ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.networkError,
          message: ParentBusLocationCopy.networkError,
        ),
      );
    } on ParentBusLocationParseFailure {
      _setState(
        ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.temporaryError,
          message: ParentBusLocationCopy.temporaryError,
        ),
      );
    } on ParentBusLocationUnexpectedHttpFailure {
      _setState(
        ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.temporaryError,
          message: ParentBusLocationCopy.temporaryError,
        ),
      );
    } catch (_) {
      _setState(
        ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.temporaryError,
          message: ParentBusLocationCopy.temporaryError,
        ),
      );
    } finally {
      _requestInFlight = false;
    }
  }

  void _setState(ParentBusLocationViewState next) {
    if (_disposed) {
      return;
    }
    _state = next;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    stopForegroundPolling();
    super.dispose();
  }
}
