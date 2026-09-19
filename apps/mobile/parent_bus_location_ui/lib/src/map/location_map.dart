import 'package:flutter/material.dart';

/// Point passed to a map renderer (no trip/bus/route identifiers).
class BusLocationMapPoint {
  const BusLocationMapPoint({
    required this.latitude,
    required this.longitude,
    required this.isStale,
  });

  final double latitude;
  final double longitude;
  final bool isStale;
}

typedef BusLocationMapBuilder = Widget Function(
  BuildContext context,
  BusLocationMapPoint point,
);

/// Production-safe placeholder when no map provider is configured.
class PlaceholderBusLocationMapView extends StatelessWidget {
  const PlaceholderBusLocationMapView({required this.point, super.key});

  final BusLocationMapPoint point;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: point.isStale
          ? 'Bus location on map, last update may be outdated'
          : 'Bus location on map, updated recently',
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: theme.colorScheme.outlineVariant),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.directions_bus_filled,
                size: 48,
                color: point.isStale ? theme.colorScheme.tertiary : theme.colorScheme.primary,
                semanticLabel: 'Bus marker',
              ),
              const SizedBox(height: 8),
              Text(
                'Current bus location',
                style: theme.textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              Text(
                '${point.latitude.toStringAsFixed(5)}, ${point.longitude.toStringAsFixed(5)}',
                style: theme.textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

Widget defaultBusLocationMapBuilder(BuildContext context, BusLocationMapPoint point) {
  return PlaceholderBusLocationMapView(point: point);
}

String formatLocationTimestamp(DateTime value, {required DateTime now}) {
  final local = value.toLocal();
  final time =
      '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  if (local.year == now.year && local.month == now.month && local.day == now.day) {
    return 'Last update today at $time';
  }
  return 'Last update ${local.year}-${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} at $time';
}
