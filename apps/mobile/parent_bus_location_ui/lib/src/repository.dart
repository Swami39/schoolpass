import 'package:parent_transport/parent_transport.dart';

/// Data access boundary for the bus-location feature (wraps [ParentBusLocationApi]).
abstract class ParentBusLocationRepository {
  Future<ParentBusLocation> fetchChildBusLocation({required String studentId});
}

class ParentBusLocationApiRepository implements ParentBusLocationRepository {
  ParentBusLocationApiRepository(this._api);

  final ParentBusLocationApi _api;

  @override
  Future<ParentBusLocation> fetchChildBusLocation({required String studentId}) {
    return _api.fetchChildBusLocation(studentId: studentId);
  }
}
