import 'package:flutter/material.dart';

import '../app/attendant_app_controller.dart';
import '../trips/trip_models.dart';
import 'trip_scan_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final AttendantAppController controller;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My trips today'),
        actions: [
          IconButton(
            onPressed: controller.refreshTrips,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            onPressed: controller.logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: controller.refreshTrips,
        child: _body(context),
      ),
    );
  }

  Widget _body(BuildContext context) {
    if (controller.loadingTrips && controller.trips.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 120),
          Center(child: CircularProgressIndicator()),
        ],
      );
    }
    final error = controller.errorMessage;
    if (controller.trips.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          if (error != null)
            Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 12),
          const Text('No trips assigned for today. Ask admin to schedule a trip for your attendant profile.'),
        ],
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: controller.trips.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final trip = controller.trips[index];
        return _TripTile(controller: controller, trip: trip);
      },
    );
  }
}

class _TripTile extends StatelessWidget {
  const _TripTile({required this.controller, required this.trip});

  final AttendantAppController controller;
  final AttendantTrip trip;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(trip.displayLabel),
      subtitle: Text(trip.id),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        controller.selectTrip(trip);
        if (trip.canStartBoarding) {
          final started = await controller.startBoarding(trip);
          if (started == null || !context.mounted) return;
          if (!started.canScan) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Trip updated — open again if boarding did not start.')),
            );
            return;
          }
          Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => TripScanScreen(controller: controller, trip: started),
            ),
          );
          return;
        }
        if (!trip.canScan) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Trip is ${trip.status}; boarding must be started first.')),
          );
          return;
        }
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => TripScanScreen(controller: controller, trip: trip),
          ),
        );
      },
    );
  }
}
