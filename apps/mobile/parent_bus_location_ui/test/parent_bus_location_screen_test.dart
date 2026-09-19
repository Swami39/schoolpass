import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:parent_bus_location_ui/parent_bus_location_ui.dart';
import 'package:parent_transport/parent_transport.dart';

import 'fakes.dart';

void main() {
  const studentId = '550e8400-e29b-41d4-a716-446655440000';

  Widget wrap(Widget child) {
    return MaterialApp(home: child);
  }

  ParentBusLocationScreen screen(
    FakeBusLocationRepository repo, {
    Duration pollInterval = const Duration(days: 1),
    bool enableForegroundPolling = true,
  }) {
    return ParentBusLocationScreen(
      studentId: studentId,
      repository: repo,
      pollInterval: pollInterval,
      enableForegroundPolling: enableForegroundPolling,
    );
  }

  group('ParentBusLocationScreen', () {
    testWidgets('A loading state', (tester) async {
      final repo = FakeBusLocationRepository((_) async {
        await Future<void>.delayed(const Duration(milliseconds: 200));
        return availableLocation();
      });
      await tester.pumpWidget(wrap(screen(repo, enableForegroundPolling: false)));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text(ParentBusLocationCopy.loading), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('B available state shows marker and update time without internal ids', (tester) async {
      final occurred = DateTime.now().toUtc().subtract(const Duration(seconds: 30));
      final repo = FakeBusLocationRepository((_) async => availableLocation(occurredAt: occurred));
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.directions_bus_filled), findsOneWidget);
      expect(find.textContaining('Last update'), findsOneWidget);
      expect(find.textContaining('tenant'), findsNothing);
      expect(find.textContaining('guardian'), findsNothing);
      expect(find.textContaining('trip_id'), findsNothing);
      expect(find.textContaining('bus_id'), findsNothing);
    });

    testWidgets('C noAssignment message', (tester) async {
      final repo = FakeBusLocationRepository(
        (_) async => ParentBusLocation(
          studentId: studentId,
          status: ParentBusLocationStatus.noAssignment,
        ),
      );
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.noAssignment), findsOneWidget);
    });

    testWidgets('D noActiveTrip message', (tester) async {
      final repo = FakeBusLocationRepository(
        (_) async => ParentBusLocation(
          studentId: studentId,
          status: ParentBusLocationStatus.noActiveTrip,
        ),
      );
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.noActiveTrip), findsOneWidget);
    });

    testWidgets('E locationUnavailable message', (tester) async {
      final repo = FakeBusLocationRepository(
        (_) async => ParentBusLocation(
          studentId: studentId,
          status: ParentBusLocationStatus.locationUnavailable,
        ),
      );
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.locationUnavailable), findsOneWidget);
      expect(find.textContaining('Redis'), findsNothing);
    });

    testWidgets('F cacheUnavailable message', (tester) async {
      final repo = FakeBusLocationRepository(
        (_) async => ParentBusLocation(
          studentId: studentId,
          status: ParentBusLocationStatus.cacheUnavailable,
        ),
      );
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.cacheUnavailable), findsOneWidget);
      expect(find.textContaining('Redis'), findsNothing);
    });

    testWidgets('G network failure', (tester) async {
      final repo = FakeBusLocationRepository((_) async => throw ParentBusLocationNetworkFailure());
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.networkError), findsOneWidget);
    });

    testWidgets('H not found handling', (tester) async {
      final repo = FakeBusLocationRepository((_) async => throw ParentBusLocationNotFoundFailure());
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.notFound), findsOneWidget);
    });

    testWidgets('I manual refresh triggers API again', (tester) async {
      final repo = FakeBusLocationRepository((_) async => availableLocation());
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(repo.callCount, 1);
      await tester.tap(find.byTooltip(ParentBusLocationCopy.refreshLabel));
      await tester.pumpAndSettle();
      expect(repo.callCount, 2);
    });

    testWidgets('J polling starts while active and stops on dispose', (tester) async {
      final repo = FakeBusLocationRepository((_) async => availableLocation());
      await tester.pumpWidget(wrap(screen(repo, pollInterval: const Duration(milliseconds: 30))));
      await tester.pumpAndSettle();
      final afterFirst = repo.callCount;
      await tester.pump(const Duration(milliseconds: 35));
      await tester.pumpAndSettle();
      expect(repo.callCount, greaterThan(afterFirst));
      await tester.pumpWidget(const SizedBox.shrink());
      final onDispose = repo.callCount;
      await tester.pump(const Duration(milliseconds: 100));
      expect(repo.callCount, onDispose);
    });

    testWidgets('K student_id passed to repository', (tester) async {
      final repo = FakeBusLocationRepository((_) async => availableLocation());
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(repo.lastStudentId, studentId);
    });

    testWidgets('L UI does not send tenant or trip parameters', (tester) async {
      final repo = FakeBusLocationRepository((_) async => availableLocation());
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(repo.lastStudentId, studentId);
      expect(repo.callCount, 1);
    });

    testWidgets('M malformed available never shows fabricated coordinates', (tester) async {
      final repo = FakeBusLocationRepository(
        (_) async => ParentBusLocation(
          studentId: studentId,
          status: ParentBusLocationStatus.available,
        ),
      );
      await tester.pumpWidget(wrap(screen(repo)));
      await tester.pumpAndSettle();
      expect(find.textContaining('12.9716'), findsNothing);
      expect(find.text(ParentBusLocationCopy.temporaryError), findsOneWidget);
    });

    testWidgets('N stale location uses server timestamp in label', (tester) async {
      final occurred = DateTime.utc(2020, 1, 1, 6, 15);
      final repo = FakeBusLocationRepository((_) async => availableLocation(occurredAt: occurred));
      await tester.pumpWidget(
        wrap(
          ParentBusLocationScreen(
            studentId: studentId,
            repository: repo,
            pollInterval: const Duration(days: 1),
            freshnessPolicy: const BusLocationFreshnessPolicy(staleAfter: Duration.zero),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(ParentBusLocationCopy.staleHint), findsOneWidget);
      expect(find.textContaining('2020-01-01'), findsOneWidget);
    });
  });
}
