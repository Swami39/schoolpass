/// Presentation-only rule for labeling a location as stale in the UI.
///
/// Does not alter server [occurredAt] / [receivedAt] values.
class BusLocationFreshnessPolicy {
  const BusLocationFreshnessPolicy({this.staleAfter = const Duration(minutes: 2)});

  final Duration staleAfter;

  bool isStale({required DateTime occurredAt, required DateTime now}) {
    return now.difference(occurredAt.toUtc()) > staleAfter;
  }
}
