import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

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
    return Scaffold(
      appBar: AppBar(
        title: const DesignAppBarTitle(
          'My trips',
          subtitle: 'Tap a trip to start boarding',
        ),
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
        SectionLabel(formatDayYear(today)),
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

  /// A trip is "live" once boarding has started or it is in progress.
  bool get _isLive {
    final status = trip.status.toLowerCase();
    return status == 'boarding' || status == 'in_progress';
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
    final date = DateTime.tryParse(trip.serviceDate);
    final dateLabel = date != null ? formatDay(date) : trip.serviceDate;
    final title = '${prettifyLabel(trip.shift)} trip';

    if (_isLive) {
      // The active trip gets the CampusPass-style live hero header.
      return HeroCard(
        eyebrow: 'Live trip',
        title: title,
        subtitle: '$dateLabel · ${prettifyLabel(trip.status)}',
        live: true,
        onTap: () => _open(context),
        trailing: Icon(
          Icons.chevron_right,
          color: Colors.white.withValues(alpha: 0.9),
        ),
      );
    }

    final bus = context.status.of(StatusKind.bus);
    return Panel(
      onTap: () => _open(context),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: context.status.softOf(StatusKind.bus),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(_shiftIcon, color: bus, size: 28),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 2),
                Text(
                  dateLabel,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: DesignColors.ink2,
                  ),
                ),
                const SizedBox(height: 8),
                _StatusChip(status: trip.status),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: DesignColors.ink3),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  StatusKind get _kind {
    final s = status.toLowerCase();
    if (s == 'boarding' || s == 'in_progress') return StatusKind.bus;
    if (s.contains('cancel')) return StatusKind.absent;
    if (s == 'completed') return StatusKind.present;
    return StatusKind.neutral;
  }

  @override
  Widget build(BuildContext context) {
    return StatusPill(kind: _kind, label: prettifyLabel(status));
  }
}
