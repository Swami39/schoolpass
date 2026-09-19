import 'dart:async';

import 'package:flutter/material.dart';
import 'package:parent_transport/parent_transport.dart';

import 'bus_location_controller.dart';
import 'freshness_policy.dart';
import 'map/location_map.dart';
import 'repository.dart';
import 'view_state.dart';

/// Live bus location for one authenticated parent's child ([studentId] from navigation).
class ParentBusLocationScreen extends StatefulWidget {
  const ParentBusLocationScreen({
    required this.studentId,
    required this.repository,
    this.pollInterval = const Duration(seconds: 20),
    this.freshnessPolicy = const BusLocationFreshnessPolicy(),
    this.mapBuilder = defaultBusLocationMapBuilder,
    this.onAuthFailure,
    this.enableForegroundPolling = true,
    super.key,
  });

  /// Creates the screen using [ParentBusLocationApi] from Phase 6D.3.
  factory ParentBusLocationScreen.withApi({
    required String studentId,
    required ParentBusLocationApi api,
    Key? key,
    Duration pollInterval = const Duration(seconds: 20),
    BusLocationFreshnessPolicy freshnessPolicy = const BusLocationFreshnessPolicy(),
    BusLocationMapBuilder mapBuilder = defaultBusLocationMapBuilder,
    void Function(int statusCode)? onAuthFailure,
  }) {
    return ParentBusLocationScreen(
      key: key,
      studentId: studentId,
      repository: ParentBusLocationApiRepository(api),
      pollInterval: pollInterval,
      freshnessPolicy: freshnessPolicy,
      mapBuilder: mapBuilder,
      onAuthFailure: onAuthFailure,
    );
  }

  final String studentId;
  final ParentBusLocationRepository repository;
  final Duration pollInterval;
  final BusLocationFreshnessPolicy freshnessPolicy;
  final BusLocationMapBuilder mapBuilder;
  final void Function(int statusCode)? onAuthFailure;
  final bool enableForegroundPolling;

  @override
  State<ParentBusLocationScreen> createState() => _ParentBusLocationScreenState();
}

class _ParentBusLocationScreenState extends State<ParentBusLocationScreen> {
  late final ParentBusLocationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ParentBusLocationController(
      repository: widget.repository,
      studentId: widget.studentId,
      pollInterval: widget.pollInterval,
      freshnessPolicy: widget.freshnessPolicy,
      onAuthFailure: widget.onAuthFailure,
    )..addListener(_onControllerChanged);
    if (widget.enableForegroundPolling) {
      _controller.startForegroundPolling();
    } else {
      unawaited(_controller.refresh());
    }
  }

  void _onControllerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _controller.removeListener(_onControllerChanged);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = _controller.state;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bus location'),
        actions: [
          IconButton(
            onPressed: _controller.state.isRefreshing ? null : () => _controller.refresh(manual: true),
            tooltip: ParentBusLocationCopy.refreshLabel,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: _Body(
            state: state,
            mapBuilder: widget.mapBuilder,
            onRetry: () => _controller.refresh(manual: true),
          ),
        ),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({
    required this.state,
    required this.mapBuilder,
    required this.onRetry,
  });

  final ParentBusLocationViewState state;
  final BusLocationMapBuilder mapBuilder;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (state.isLoading) {
      return Semantics(
        label: ParentBusLocationCopy.loading,
        liveRegion: true,
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text(ParentBusLocationCopy.loading),
            ],
          ),
        ),
      );
    }

    if (state.kind == ParentBusLocationUiKind.available && state.display != null) {
      final display = state.display!;
      final point = BusLocationMapPoint(
        latitude: display.latitude,
        longitude: display.longitude,
        isStale: display.isStale,
      );
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (state.isRefreshing) const LinearProgressIndicator(minHeight: 2),
          Expanded(child: mapBuilder(context, point)),
          const SizedBox(height: 12),
          _UpdateMeta(display: display),
        ],
      );
    }

    return _MessagePanel(
      state: state,
      onRetry: onRetry,
    );
  }
}

class _UpdateMeta extends StatelessWidget {
  const _UpdateMeta({required this.display});

  final ParentBusLocationDisplay display;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final now = DateTime.now();
    final freshnessText =
        display.isStale ? ParentBusLocationCopy.staleHint : ParentBusLocationCopy.recentHint;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          formatLocationTimestamp(display.occurredAt, now: now),
          style: theme.textTheme.bodyLarge,
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            Icon(
              display.isStale ? Icons.schedule : Icons.check_circle_outline,
              size: 18,
              color: display.isStale ? theme.colorScheme.tertiary : theme.colorScheme.primary,
            ),
            const SizedBox(width: 6),
            Expanded(child: Text(freshnessText, style: theme.textTheme.bodyMedium)),
          ],
        ),
        if (display.accuracyMeters != null) ...[
          const SizedBox(height: 4),
          Text(
            'Accuracy about ${display.accuracyMeters!.toStringAsFixed(0)} m',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ],
    );
  }
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({required this.state, required this.onRetry});

  final ParentBusLocationViewState state;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final showRetry = state.kind == ParentBusLocationUiKind.networkError ||
        state.kind == ParentBusLocationUiKind.temporaryError ||
        state.kind == ParentBusLocationUiKind.cacheUnavailable ||
        state.kind == ParentBusLocationUiKind.locationUnavailable;

    return Semantics(
      liveRegion: true,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (state.isRefreshing) const LinearProgressIndicator(minHeight: 2),
          Icon(Icons.info_outline, size: 40, color: theme.colorScheme.primary),
          const SizedBox(height: 12),
          Text(
            state.message ?? ParentBusLocationCopy.temporaryError,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge,
          ),
          if (showRetry) ...[
            const SizedBox(height: 16),
            FilledButton(
              onPressed: state.isRefreshing ? null : onRetry,
              child: const Text('Try again'),
            ),
          ],
        ],
      ),
    );
  }
}
