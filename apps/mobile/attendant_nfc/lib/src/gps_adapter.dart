import 'dart:async';

import 'gps_models.dart';

abstract class GpsAdapter {
  Stream<GpsPosition> get positions;
}

class FakeGpsAdapter implements GpsAdapter {
  FakeGpsAdapter();

  final StreamController<GpsPosition> _controller =
      StreamController<GpsPosition>.broadcast();

  @override
  Stream<GpsPosition> get positions => _controller.stream;

  void emit(GpsPosition position) => _controller.add(position);

  void close() => _controller.close();
}
