import 'dart:async';
import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:nfc_manager/nfc_manager.dart';
import 'package:nfc_manager/nfc_manager_android.dart';
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import 'format.dart';
import 'teacher_widgets.dart';

/// NFC class attendance with offline outbox.
///
/// Primary flow is tap-to-scan via the phone's NFC reader; manual UID entry
/// remains as a fallback for phones without NFC.
class NfcAttendanceScreen extends StatefulWidget {
  const NfcAttendanceScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  State<NfcAttendanceScreen> createState() => _NfcAttendanceScreenState();
}

class _NfcAttendanceScreenState extends State<NfcAttendanceScreen> {
  final _uid = TextEditingController();
  TeacherClassNfcOutboxStore? _store;
  TeacherClassNfcEventService? _service;
  String? _error;
  String? _status;
  String? _syncState;
  bool _booting = true;
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
  Future<String> _outboxDbPath(String sectionId) async {
    final fileName = 'schoolpass_teacher_nfc_$sectionId.db';
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
      final TeacherClassNfcOutboxStore store;
      if (kIsWeb) {
        store = TeacherClassNfcOutboxStore.openInMemory();
      } else {
        store = TeacherClassNfcOutboxStore.open(
          path: await _outboxDbPath(widget.clazz.sectionId),
        );
      }
      store.recoverSyncingToPending();
      final section = SectionContext()..setSection(widget.clazz.sectionId);
      final worker = TeacherClassNfcSyncWorker(
        store: store,
        client: widget.controller.deps.nfcSyncClient,
        clientDeviceId: deviceId,
      );
      final service = TeacherClassNfcEventService(
        store: store,
        sectionContext: section,
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
      unawaited(_detectNfc());
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not register device for NFC sync.';
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
      _syncState = null;
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
      _syncState = null;
    });
    try {
      final event = await service.recordScanAndTrySync(cardUid: uid);
      if (!mounted) return;
      setState(() {
        _scanCount++;
        _status = 'Scan recorded for ${widget.clazz.displayLabel}';
        _syncState = event.syncState.name;
        if (event.rejectionCode != null) {
          _error = 'Rejected: ${prettifyLabel(event.rejectionCode!)}';
        }
      });
    } on NoActiveSectionError {
      if (!mounted) return;
      setState(() {
        _status = null;
        _error = 'No active class section.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _status = null;
        _error = 'Scan failed. Please try again.';
      });
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
    _store?.close();
    super.dispose();
  }

  Widget _syncChip(String state) {
    final scheme = Theme.of(context).colorScheme;
    switch (state) {
      case 'synced':
        return const StatusChip(
          label: 'Synced',
          color: Color(0xFF15803D),
          icon: Icons.cloud_done_outlined,
        );
      case 'pending':
        return StatusChip(
          label: 'Queued offline',
          color: scheme.onSurfaceVariant,
          icon: Icons.cloud_off_outlined,
        );
      case 'rejected':
        return StatusChip(
          label: 'Rejected',
          color: scheme.error,
          icon: Icons.cloud_off_outlined,
        );
      default:
        return StatusChip(
          label: prettifyLabel(state),
          color: scheme.onSurfaceVariant,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text('NFC · ${widget.clazz.displayLabel}')),
      body: _booting
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
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
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            TextField(
                              controller: _uid,
                              decoration: const InputDecoration(
                                labelText: 'HF card UID',
                                prefixIcon: Icon(Icons.contactless_outlined),
                              ),
                              textCapitalization: TextCapitalization.characters,
                              onSubmitted: (_) => _submitManual(),
                            ),
                            const SizedBox(height: 12),
                            FilledButton.icon(
                              onPressed: _submitManual,
                              icon: const Icon(Icons.tap_and_play),
                              label: const Text('Record scan'),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Scans are stored on this device and synced when you are back online.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                if (_status != null) ...[
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          Expanded(child: Text(_status!)),
                          if (_syncState != null) _syncChip(_syncState!),
                        ],
                      ),
                    ),
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  ErrorBanner(message: _error!),
                ],
              ],
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
                      ? "Scan cards with the phone's NFC reader."
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
