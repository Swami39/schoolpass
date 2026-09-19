import 'package:parent_transport/parent_transport.dart';

import 'freshness_policy.dart';

enum ParentBusLocationUiKind {
  loading,
  available,
  noAssignment,
  noActiveTrip,
  locationUnavailable,
  cacheUnavailable,
  notFound,
  networkError,
  authError,
  temporaryError,
}

/// Parent-safe fields for map/location presentation (no internal IDs).
class ParentBusLocationDisplay {
  const ParentBusLocationDisplay({
    required this.latitude,
    required this.longitude,
    required this.occurredAt,
    required this.receivedAt,
    required this.isStale,
    this.accuracyMeters,
  });

  final double latitude;
  final double longitude;
  final DateTime occurredAt;
  final DateTime receivedAt;
  final bool isStale;
  final double? accuracyMeters;
}

class ParentBusLocationViewState {
  const ParentBusLocationViewState({
    required this.kind,
    this.display,
    this.isRefreshing = false,
    this.message,
  });

  final ParentBusLocationUiKind kind;
  final ParentBusLocationDisplay? display;
  final bool isRefreshing;
  final String? message;

  bool get isLoading => kind == ParentBusLocationUiKind.loading && !isRefreshing;

  static ParentBusLocationViewState loading({bool isRefreshing = false}) {
    return ParentBusLocationViewState(
      kind: ParentBusLocationUiKind.loading,
      isRefreshing: isRefreshing,
    );
  }

  static ParentBusLocationViewState fromLocation(
    ParentBusLocation location, {
    required BusLocationFreshnessPolicy freshnessPolicy,
    required DateTime now,
    bool isRefreshing = false,
  }) {
    switch (location.status) {
      case ParentBusLocationStatus.available:
        final coords = location.coordinates;
        if (coords == null) {
          return ParentBusLocationViewState(
            kind: ParentBusLocationUiKind.temporaryError,
            message: ParentBusLocationCopy.temporaryError,
            isRefreshing: isRefreshing,
          );
        }
        return ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.available,
          isRefreshing: isRefreshing,
          display: ParentBusLocationDisplay(
            latitude: coords.latitude,
            longitude: coords.longitude,
            occurredAt: coords.occurredAt,
            receivedAt: coords.receivedAt,
            accuracyMeters: coords.accuracyMeters,
            isStale: freshnessPolicy.isStale(occurredAt: coords.occurredAt, now: now),
          ),
        );
      case ParentBusLocationStatus.noAssignment:
        return ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.noAssignment,
          message: ParentBusLocationCopy.noAssignment,
          isRefreshing: isRefreshing,
        );
      case ParentBusLocationStatus.noActiveTrip:
        return ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.noActiveTrip,
          message: ParentBusLocationCopy.noActiveTrip,
          isRefreshing: isRefreshing,
        );
      case ParentBusLocationStatus.locationUnavailable:
        return ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.locationUnavailable,
          message: ParentBusLocationCopy.locationUnavailable,
          isRefreshing: isRefreshing,
        );
      case ParentBusLocationStatus.cacheUnavailable:
        return ParentBusLocationViewState(
          kind: ParentBusLocationUiKind.cacheUnavailable,
          message: ParentBusLocationCopy.cacheUnavailable,
          isRefreshing: isRefreshing,
        );
    }
  }
}

/// Parent-facing copy (no backend/cache terminology).
abstract final class ParentBusLocationCopy {
  static const loading = 'Loading bus location…';
  static const noAssignment = 'No active bus assignment is available for your child right now.';
  static const noActiveTrip = "Your child's assigned bus does not have an active trip right now.";
  static const locationUnavailable =
      "Your child's bus location isn't available right now. Please try again shortly.";
  static const cacheUnavailable =
      'Location service is temporarily unavailable. Please try again shortly.';
  static const notFound = 'Unable to show bus location for this child.';
  static const networkError = 'Network error. Check your connection and try again.';
  static const temporaryError = 'Something went wrong. Please try again shortly.';
  static const refreshLabel = 'Refresh bus location';
  static const staleHint = 'This update may be outdated.';
  static const recentHint = 'Location updated recently.';
}
