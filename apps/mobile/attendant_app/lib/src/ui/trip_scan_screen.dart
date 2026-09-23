import 'dart:async';
import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:nfc_manager/nfc_manager.dart';
import 'package:nfc_manager/nfc_manager_android.dart';
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../api/attendant_errors.dart';
import '../app/attendant_app_controller.dart';
import '../gps/trip_gps_tracker.dart';
import '../trips/trip_models.dart';
import 'format.dart';
import 'widgets.dart';

/// Transport NFC boarding with offline outbox and live GPS.
///
/// Primary flow is tap-to-scan via the phone's NFC reader; manual UID entry
/// remains as a fallback for phones without NFC.
class TripScanScreen extends StatefulWidget {
  const TripScanScreen({required this.controller, required this.trip, super.key});

  final AttendantAppController controller;
  final AttendantTrip trip;

  @override
  State<TripScanScreen> createState() => _TripScanScreenState();
}

class _TripScanScreenState extends State<TripScanScreen> {
  final _uid = TextEditingController();
  NfcOutboxStore? _store;
  NfcEventService? _service;
  TripGpsTracker? _gpsTracker;
  String? _error;
  String? _status;
  bool _booting = true;
  NfcEventType _eventType = NfcEventType.boarding;
  bool _nfcAvailable = false;
  bool _nfcScanning = false;
  int _scanCount = 0;
  String? _lastUid;
  DateTime? _lastUidAt;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  /// Durable app-documents path; falls back to temp only if that fails.
  Future<String> _outboxDbPath(String tripId) async {
    final fileName = 'schoolpass_bus_nfc_$tripId.db';
    try {
      final dir = await getApplicationDocumentsDirectory();
      return '${dir.path}/$fileName';
    } catch (_) {
      return '${Directory.systemTemp.path}/$fileName';
    }
  }

  Future<void> _boot() async {
    try {
      final deviceId = await widget.controller.deps.deviceApi.registerDevice(const Uuid().v4());
      final NfcOutboxStore store;
      if (kIsWeb) {
        store = NfcOutboxStore.openInMemory();
      } else {
        store = NfcOutboxStore.open(path: await _outboxDbPath(widget.trip.id));
      }
      store.recoverSyncingToPending();
      final tripContext = MutableTripContext()
        ..setTrip(TripSelection(tripId: widget.trip.id));
      final worker = NfcSyncWorker(
        store: store,
        client: widget.controller.deps.nfcSyncClient,
        clientDeviceId: deviceId,
      );
      final service = NfcEventService(
        store: store,
        tripContext: tripContext,
        clientDeviceId: deviceId,
        syncWorker: worker,
      );
      if (!mounted) {
        store.close();
        return;
      }
      final gpsTracker = TripGpsTracker(
        tripId: widget.trip.id,
        clientDeviceId: deviceId,
        syncClient: widget.controller.deps.gpsSyncClient,
        onAuthFailure: () {
          widget.controller.logout();
        },
      );
      setState(() {
        _store = store;
        _service = service;
        _gpsTracker = gpsTracker;
        _booting = false;
      });
      // Non-blocking: permission prompts and first fix arrive async.
      unawaited(gpsTracker.start());
      unawaited(_detectNfc());
    } on AttendantUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not register this phone for NFC sync.';
        _booting = false;
      });
    }
  }

  Future<void> _detectNfc() async {
    var availability = NfcAvailability.unsupported;
    try {
      availability = await NfcManager.instance.checkAvailability();
    } catch (_) {
      // Leave as unsupported.
    }
    if (!mounted) return;
    setState(() {
      _nfcAvailable = availability == NfcAvailability.enabled;
      if (availability == NfcAvailability.disabled) {
        _error = 'NFC is turned off on this phone. Enable it in Settings to scan cards.';
      }
    });
  }

  Future<void> _startNfcScanning() async {
    if (_nfcScanning) return;
    setState(() {
      _nfcScanning = true;
      _error = null;
      _status = 'Hold a student card near the phone…';
    });
    try {
      await NfcManager.instance.startSession(
        pollingOptions: {
          NfcPollingOption.iso14443,
          NfcPollingOption.iso15693,
          NfcPollingOption.iso18092,
        },
        onDiscovered: (NfcTag tag) {
          final id = NfcTagAndroid.from(tag)?.id;
          if (id == null || id.isEmpty) {
            if (mounted) {
              setState(() => _error = 'Card detected, but its UID could not be read.');
            }
            return;
          }
          final uid = id.map((b) => b.toRadixString(16).padLeft(2, '0')).join().toUpperCase();
          unawaited(_recordNfcUid(uid));
        },
      );
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _nfcScanning = false;
        _error = 'Could not start NFC scanning.';
      });
    }
  }

  Future<void> _stopNfcScanning() async {
    try {
      await NfcManager.instance.stopSession();
    } catch (_) {
      // No active session — nothing to stop.
    }
    if (mounted) {
      setState(() => _nfcScanning = false);
    }
  }

  /// Debounces a card held against the phone so it is not recorded twice.
  Future<void> _recordNfcUid(String uid) async {
    final now = DateTime.now();
    if (_lastUid == uid &&
        _lastUidAt != null &&
        now.difference(_lastUidAt!) < const Duration(seconds: 4)) {
      return;
    }
    _lastUid = uid;
    _lastUidAt = now;
    await _recordScan(uid);
  }

  Future<void> _recordScan(String uid) async {
    final service = _service;
    if (service == null || !mounted) return;
    setState(() {
      _error = null;
      _status = 'Recording $uid…';
    });
    try {
      final event = await service.recordScanAndTrySync(cardUid: uid, eventType: _eventType);
      if (!mounted) return;
      setState(() {
        _scanCount++;
        _status =
            '${prettifyLabel(_eventType.name)} recorded · seq ${event.deviceSequence} · ${event.syncState.name}';
        if (event.rejectionCode != null) {
          _error = 'Rejected: ${event.rejectionCode}';
        }
      });
    } on NoActiveTripError {
      if (!mounted) return;
      setState(() => _error = 'No active trip context.');
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Scan failed. Please try again.');
    }
  }

  Future<void> _submitManual() async {
    final raw = _uid.text.trim();
    if (raw.isEmpty) return;
    FocusScope.of(context).unfocus();
    await _recordScan(raw);
    _uid.clear();
  }

  @override
  void dispose() {
    _uid.dispose();
    NfcManager.instance.stopSession().ignore();
    final tracker = _gpsTracker;
    _gpsTracker = null;
    if (tracker != null) {
      // stop() does a best-effort final flush; dispose() releases resources.
      unawaited(tracker.stop());
      tracker.dispose();
    }
    _store?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text('${prettifyLabel(widget.trip.shift)} trip')),
      body: _booting
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _TripHeaderCard(trip: widget.trip),
                  const SizedBox(height: 12),
                  if (_gpsTracker != null) ...[
                    ValueListenableBuilder<GpsTrackerSnapshot>(
                      valueListenable: _gpsTracker!.snapshot,
                      builder: (context, snap, _) => _GpsStatusCard(snapshot: snap),
                    ),
                    const SizedBox(height: 12),
                  ],
                  Text('Recording', style: theme.textTheme.titleSmall),
                  const SizedBox(height: 8),
                  SegmentedButton<NfcEventType>(
                    segments: const [
                      ButtonSegment(
                        value: NfcEventType.boarding,
                        label: Text('Boarding'),
                        icon: Icon(Icons.arrow_upward_outlined),
                      ),
                      ButtonSegment(
                        value: NfcEventType.dropoff,
                        label: Text('Drop-off'),
                        icon: Icon(Icons.arrow_downward_outlined),
                      ),
                    ],
                    selected: {_eventType},
                    onSelectionChanged: (s) => setState(() => _eventType = s.first),
                  ),
                  const SizedBox(height: 12),
                  _NfcScanCard(
                    available: _nfcAvailable,
                    scanning: _nfcScanning,
                    scanCount: _scanCount,
                    onStart: _startNfcScanning,
                    onStop: _stopNfcScanning,
                  ),
                  const SizedBox(height: 12),
                  Card(
                    child: ExpansionTile(
                      leading: const Icon(Icons.keyboard_outlined),
                      title: const Text('Enter card UID manually'),
                      subtitle: const Text('Fallback for phones without NFC'),
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                          child: Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _uid,
                                  decoration: const InputDecoration(labelText: 'Card UID'),
                                  textCapitalization: TextCapitalization.characters,
                                  onSubmitted: (_) => _submitManual(),
                                ),
                              ),
                              const SizedBox(width: 8),
                              FilledButton(
                                onPressed: _submitManual,
                                child: const Text('Record'),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (_status != null) ...[
                    const SizedBox(height: 12),
                    _StatusLine(text: _status!),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    ErrorBanner(message: _error!),
                  ],
                ],
              ),
            ),
    );
  }
}

class _TripHeaderCard extends StatelessWidget {
  const _TripHeaderCard({required this.trip});

  final AttendantTrip trip;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final date = DateTime.tryParse(trip.serviceDate);
    return Card(
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
              child: Icon(Icons.directions_bus, color: scheme.onPrimaryContainer, size: 28),
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
                    style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: scheme.secondaryContainer,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                prettifyLabel(trip.status),
                style: TextStyle(
                  color: scheme.onSecondaryContainer,
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NfcScanCard extends StatelessWidget {
  const _NfcScanCard({
    required this.available,
    required this.scanning,
    required this.scanCount,
    required this.onStart,
    required this.onStop,
  });

  final bool available;
  final bool scanning;
  final int scanCount;
  final VoidCallback onStart;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: scanning ? scheme.primary : scheme.primaryContainer,
              ),
              child: Icon(
                Icons.nfc_outlined,
                size: 44,
                color: scanning ? scheme.onPrimary : scheme.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              scanning ? 'Ready to scan' : 'Tap student cards',
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              scanning
                  ? 'Hold each card near the back of the phone.'
                  : available
                      ? 'Scan cards with the phone\'s NFC reader.'
                      : 'NFC is not available on this phone — use manual entry below.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
            ),
            const SizedBox(height: 16),
            if (scanning)
              OutlinedButton.icon(
                onPressed: onStop,
                icon: const Icon(Icons.stop_outlined),
                label: const Text('Stop scanning'),
              )
            else
              FilledButton.icon(
                onPressed: available ? onStart : null,
                icon: const Icon(Icons.nfc_outlined),
                label: const Text('Start scanning'),
              ),
            if (scanCount > 0) ...[
              const SizedBox(height: 8),
              Text(
                'Scans this session: $scanCount',
                style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusLine extends StatelessWidget {
  const _StatusLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        Icon(Icons.check_circle_outline, size: 18, color: scheme.primary),
        const SizedBox(width: 8),
        Expanded(child: Text(text)),
      ],
    );
  }
}

/// Live status of trip GPS sharing shown on the scan screen.
class _GpsStatusCard extends StatelessWidget {
  const _GpsStatusCard({required this.snapshot});

  final GpsTrackerSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    IconData icon;
    String text;
    var warning = false;
    switch (snapshot.phase) {
      case GpsTrackerPhase.starting:
        icon = Icons.gps_not_fixed;
        text = 'GPS: starting…';
      case GpsTrackerPhase.tracking:
        icon = Icons.gps_fixed;
        text = 'GPS: sharing bus location · ${snapshot.syncedCount} sent';
        if (snapshot.pendingCount > 0) {
          text += ' · ${snapshot.pendingCount} pending';
        }
      case GpsTrackerPhase.permissionDenied:
      case GpsTrackerPhase.serviceDisabled:
      case GpsTrackerPhase.error:
        icon = Icons.gps_off;
        text = snapshot.message ?? 'GPS unavailable.';
        warning = true;
      case GpsTrackerPhase.stopped:
        icon = Icons.gps_off;
        text = 'GPS: stopped.';
    }
    return Card(
      child: ListTile(
        leading: Icon(icon, color: warning ? theme.colorScheme.error : null),
        title: Text(text, style: theme.textTheme.bodyMedium),
        subtitle: snapshot.lastFixAt != null && snapshot.phase == GpsTrackerPhase.tracking
            ? Text(
                'Last fix ${snapshot.lastFixAt!.toLocal().toString().split('.').first}',
              )
            : null,
      ),
    );
  }
}
