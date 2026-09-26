import 'dart:async';
import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:nfc_manager/nfc_manager.dart';
import 'package:nfc_manager/nfc_manager_android.dart';
import 'package:path_provider/path_provider.dart';
import 'package:schoolpass_design/schoolpass_design.dart' as design;
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
    final String deviceId;
    try {
      deviceId =
          await widget.controller.deps.deviceApi.registerDevice(const Uuid().v4());
    } on TeacherUnauthorized {
      await widget.controller.logout();
      return;
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error =
            'Could not register this device with the server. Check your connection and try again. ($e)';
        _booting = false;
      });
      return;
    }
    try {
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
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not open the on-device scan storage. ($e)';
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
    switch (state) {
      case 'synced':
        return const design.StatusPill(
          kind: design.StatusKind.present,
          label: 'Synced',
        );
      case 'pending':
        return const design.StatusPill(
          kind: design.StatusKind.neutral,
          label: 'Queued offline',
        );
      case 'rejected':
        return const design.StatusPill(
          kind: design.StatusKind.absent,
          label: 'Rejected',
        );
      default:
        return design.StatusPill(
          kind: design.StatusKind.neutral,
          label: prettifyLabel(state),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
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
                design.Panel(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
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
                            design.PrimaryButton(
                              label: 'Record scan',
                              icon: Icons.tap_and_play,
                              onPressed: _submitManual,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Scans are stored on this device and synced when you are back online.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: design.DesignColors.ink2,
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
                  design.Panel(
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
    return design.Panel(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: scanning
                    ? design.DesignColors.brand
                    : design.DesignColors.brandSoft,
              ),
              child: Icon(
                Icons.nfc_outlined,
                size: 44,
                color: scanning ? Colors.white : design.DesignColors.brandInk,
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
                      : 'NFC is not available on this phone \u2014 use manual entry below.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: design.DesignColors.ink2,
              ),
            ),
            const SizedBox(height: 16),
            if (scanning)
              OutlinedButton.icon(
                onPressed: onStop,
                icon: const Icon(Icons.stop_outlined),
                label: const Text('Stop scanning'),
              )
            else
              design.PrimaryButton(
                label: 'Start scanning',
                icon: Icons.nfc_outlined,
                onPressed: available ? onStart : null,
              ),
            if (scanCount > 0) ...[
              const SizedBox(height: 8),
              Text(
                'Scans this session: $scanCount',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: design.DesignColors.ink3,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
