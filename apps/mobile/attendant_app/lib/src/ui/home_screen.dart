import 'package:flutter/material.dart';

import '../app/attendant_app_controller.dart';
import '../trips/trip_models.dart';
import 'format.dart';
import 'trip_scan_screen.dart';
import 'widgets.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final AttendantAppController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('My trips'),
        actions: [
          IconButton(
            onPressed: controller.refreshTrips,
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh_outlined),
          ),
          IconButton(
            onPressed: controller.logout,
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout_outlined),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: controller.refreshTrips,
        child: _body(context, theme),
      ),
    );
  }

  Widget _body(BuildContext context, ThemeData theme) {
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
        padding: const EdgeInsets.all(16),
        children: [
          if (error != null) ...[
            ErrorBanner(message: error),
            const SizedBox(height: 12),
          ],
          const EmptyState(
            icon: Icons.directions_bus_outlined,
            title: 'No trips today',
            subtitle: 'Ask your school admin to schedule a trip for your attendant profile.',
          ),
        ],
      );
    }
    final today = DateTime.now();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (error != null) ...[
          ErrorBanner(message: error),
          const SizedBox(height: 12),
        ],
        Text(
          formatDayYear(today),
          style: theme.textTheme.titleSmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 8),
        for (final trip in controller.trips) ...[
          _TripCard(controller: controller, trip: trip),
          const SizedBox(height: 12),
        ],
      ],
    );
  }
}

class _TripCard extends StatelessWidget {
  const _TripCard({required this.controller, required this.trip});

  final AttendantAppController controller;
  final AttendantTrip trip;

  IconData get _shiftIcon {
    final shift = trip.shift.toLowerCase();
    if (shift.contains('morn')) return Icons.wb_sunny_outlined;
    if (shift.contains('even') || shift.contains('afternoon')) return Icons.wb_twilight_outlined;
    return Icons.directions_bus_outlined;
  }

  Future<void> _open(BuildContext context) async {
    controller.selectTrip(trip);
    if (trip.canStartBoarding) {
      final started = await controller.startBoarding(trip);
      if (started == null || !context.mounted) return;
      if (!started.canScan) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Trip updated — open it again to start scanning.')),
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
        SnackBar(content: Text('Trip is ${prettifyLabel(trip.status)} — boarding must be started first.')),
      );
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => TripScanScreen(controller: controller, trip: trip),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final date = DateTime.tryParse(trip.serviceDate);
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _open(context),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(_shiftIcon, color: scheme.onPrimaryContainer, size: 28),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${prettifyLabel(trip.shift)} trip',
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      date != null ? formatDay(date) : trip.serviceDate,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 8),
                    _StatusChip(status: trip.status),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final s = status.toLowerCase();
    late final Color bg;
    late final Color fg;
    late final IconData icon;
    if (s == 'boarding') {
      bg = const Color(0xFFE6F4EA);
      fg = const Color(0xFF137333);
      icon = Icons.nfc_outlined;
    } else if (s == 'in_progress') {
      bg = const Color(0xFFFEF7E0);
      fg = const Color(0xFF7A4A00);
      icon = Icons.directions_bus;
    } else if (s == 'scheduled') {
      bg = const Color(0xFFE8F0FE);
      fg = const Color(0xFF174EA6);
      icon = Icons.schedule_outlined;
    } else if (s == 'completed') {
      bg = const Color(0xFFE8EAED);
      fg = const Color(0xFF3C4043);
      icon = Icons.check_circle_outline;
    } else if (s.contains('cancel')) {
      bg = const Color(0xFFFCE8E6);
      fg = const Color(0xFFA50E0E);
      icon = Icons.cancel_outlined;
    } else {
      bg = const Color(0xFFE8EAED);
      fg = const Color(0xFF3C4043);
      icon = Icons.info_outline;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fg),
          const SizedBox(width: 4),
          Text(
            prettifyLabel(status),
            style: TextStyle(color: fg, fontWeight: FontWeight.w600, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
