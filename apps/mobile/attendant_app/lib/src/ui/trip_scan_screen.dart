import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api/attendant_errors.dart';
import '../app/attendant_app_controller.dart';
import '../trips/trip_models.dart';

/// Transport NFC boarding with offline outbox (manual UID until platform NFC is wired).
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
  String? _error;
  String? _status;
  bool _booting = true;
  NfcEventType _eventType = NfcEventType.boarding;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    try {
      final deviceId = await widget.controller.deps.deviceApi.registerDevice(const Uuid().v4());
      final NfcOutboxStore store;
      if (kIsWeb) {
        store = NfcOutboxStore.openInMemory();
      } else {
        final dbPath =
            '${Directory.systemTemp.path}/schoolpass_bus_nfc_${widget.trip.id}.db';
        store = NfcOutboxStore.open(path: dbPath);
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
      setState(() {
        _store = store;
        _service = service;
        _booting = false;
      });
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

  @override
  void dispose() {
    _uid.dispose();
    _store?.close();
    super.dispose();
  }

  Future<void> _scan() async {
    final service = _service;
    if (service == null) return;
    final raw = _uid.text.trim();
    if (raw.isEmpty) return;
    setState(() {
      _error = null;
      _status = 'Recording scan…';
    });
    try {
      final event = await service.recordScanAndTrySync(cardUid: raw, eventType: _eventType);
      if (!mounted) return;
      setState(() {
        _status = '${event.syncState.name} · seq ${event.deviceSequence}';
        if (event.rejectionCode != null) {
          _error = 'Rejected: ${event.rejectionCode}';
        }
      });
      _uid.clear();
    } on NoActiveTripError {
      setState(() => _error = 'No active trip context.');
    } catch (_) {
      setState(() => _error = 'Scan failed.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Bus NFC · ${widget.trip.shift}')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _booting
            ? const Center(child: CircularProgressIndicator())
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('Trip ${widget.trip.id}', style: Theme.of(context).textTheme.bodySmall),
                  const SizedBox(height: 8),
                  SegmentedButton<NfcEventType>(
                    segments: const [
                      ButtonSegment(value: NfcEventType.boarding, label: Text('Boarding')),
                      ButtonSegment(value: NfcEventType.dropoff, label: Text('Drop-off')),
                    ],
                    selected: {_eventType},
                    onSelectionChanged: (s) => setState(() => _eventType = s.first),
                  ),
                  const SizedBox(height: 12),
                  const Text('Enter HF card UID (tap NFC hardware when integrated).'),
                  TextField(
                    controller: _uid,
                    decoration: const InputDecoration(labelText: 'Card UID'),
                    onSubmitted: (_) => _scan(),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(onPressed: _scan, child: const Text('Record scan')),
                  if (_status != null) Text(_status!),
                  if (_error != null)
                    Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
              ),
      ),
    );
  }
}
