/// Current trip (and optional stop) for bus NFC events.
class TripSelection {
  const TripSelection({
    required this.tripId,
    this.tripStopId,
  });

  final String tripId;
  final String? tripStopId;
}

abstract class TripContext {
  TripSelection? get currentTrip;
}

class MutableTripContext implements TripContext {
  MutableTripContext([this._current]);

  TripSelection? _current;

  @override
  TripSelection? get currentTrip => _current;

  void setTrip(TripSelection? selection) {
    _current = selection;
  }
}
