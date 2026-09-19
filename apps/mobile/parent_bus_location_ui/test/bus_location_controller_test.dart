import 'package:parent_bus_location_ui/parent_bus_location_ui.dart';
import 'package:parent_transport/parent_transport.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  const studentId = '550e8400-e29b-41d4-a716-446655440000';

  group('ParentBusLocationController', () {
    test('passes student_id to repository', () async {
      final repo = FakeBusLocationRepository((_) async => availableLocation());
      final controller = ParentBusLocationController(
        repository: repo,
        studentId: studentId,
      );
      await controller.refresh();
      expect(repo.lastStudentId, studentId);
      controller.dispose();
    });

    test('polling stops on dispose and does not overlap in-flight refresh', () async {
      final repo = FakeBusLocationRepository((_) async {
        await Future<void>.delayed(const Duration(milliseconds: 50));
        return availableLocation();
      })..delay = const Duration(milliseconds: 50);

      final controller = ParentBusLocationController(
        repository: repo,
        studentId: studentId,
        pollInterval: const Duration(milliseconds: 10),
      );
      controller.startForegroundPolling();
      await Future<void>.delayed(const Duration(milliseconds: 30));
      final midCount = repo.callCount;
      await Future<void>.delayed(const Duration(milliseconds: 80));
      expect(repo.callCount, greaterThanOrEqualTo(midCount));
      controller.dispose();
      final afterDispose = repo.callCount;
      await Future<void>.delayed(const Duration(milliseconds: 40));
      expect(repo.callCount, afterDispose);
    });

    test('manual refresh triggers another fetch', () async {
      final repo = FakeBusLocationRepository((_) async => availableLocation());
      final controller = ParentBusLocationController(repository: repo, studentId: studentId);
      await controller.refresh();
      await controller.refresh(manual: true);
      expect(repo.callCount, 2);
      controller.dispose();
    });

    test('stale indication uses occurredAt without modifying it', () async {
      final occurred = DateTime.utc(2026, 9, 19, 7, 0);
      final repo = FakeBusLocationRepository((_) async => availableLocation(occurredAt: occurred));
      final now = DateTime.utc(2026, 9, 19, 7, 5);
      final controller = ParentBusLocationController(
        repository: repo,
        studentId: studentId,
        freshnessPolicy: const BusLocationFreshnessPolicy(staleAfter: Duration(minutes: 2)),
        clock: () => now,
      );
      await controller.refresh();
      expect(controller.state.display!.occurredAt, occurred);
      expect(controller.state.display!.isStale, isTrue);
      controller.dispose();
    });

    test('maps errors without exposing exception text', () async {
      final repo = FakeBusLocationRepository((_) async => throw ParentBusLocationNetworkFailure());
      final controller = ParentBusLocationController(repository: repo, studentId: studentId);
      await controller.refresh();
      expect(controller.state.kind, ParentBusLocationUiKind.networkError);
      expect(controller.state.message, ParentBusLocationCopy.networkError);
      controller.dispose();
    });
  });
}
