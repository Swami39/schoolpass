import 'package:parent_bus_location_ui/parent_bus_location_ui.dart';
import 'package:parent_transport/parent_transport.dart';

class FakeBusLocationRepository implements ParentBusLocationRepository {
  FakeBusLocationRepository(this._handler);

  int callCount = 0;
  String? lastStudentId;
  Future<ParentBusLocation> Function(String studentId) _handler;
  Duration? delay;

  void setHandler(Future<ParentBusLocation> Function(String studentId) handler) {
    _handler = handler;
  }

  @override
  Future<ParentBusLocation> fetchChildBusLocation({required String studentId}) async {
    callCount += 1;
    lastStudentId = studentId;
    if (delay != null) {
      await Future<void>.delayed(delay!);
    }
    return _handler(studentId);
  }
}

ParentBusLocation availableLocation({
  DateTime? occurredAt,
  double lat = 12.9716,
  double lon = 77.5946,
}) {
  final at = occurredAt ?? DateTime.utc(2026, 9, 19, 8, 0);
  return ParentBusLocation(
    studentId: '550e8400-e29b-41d4-a716-446655440000',
    status: ParentBusLocationStatus.available,
    coordinates: ParentBusLocationCoordinates(
      latitude: lat,
      longitude: lon,
      occurredAt: at,
      receivedAt: at.add(const Duration(seconds: 1)),
      accuracyMeters: 12,
    ),
  );
}
