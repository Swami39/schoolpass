import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';

/// NFC attendance with offline outbox (manual UID entry until platform NFC is wired).
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
  bool _booting = true;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    try {
      final deviceId = await widget.controller.deps.deviceApi.registerDevice(const Uuid().v4());
      final TeacherClassNfcOutboxStore store;
      if (kIsWeb) {
        store = TeacherClassNfcOutboxStore.openInMemory();
      } else {
        final dbPath = '${Directory.systemTemp.path}/schoolpass_teacher_nfc_${widget.clazz.sectionId}.db';
        store = TeacherClassNfcOutboxStore.open(path: dbPath);
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
      final event = await service.recordScanAndTrySync(cardUid: raw);
      if (!mounted) return;
      setState(() {
        _status = 'Event ${event.clientEventId} · ${event.syncState.name}';
        if (event.rejectionCode != null) {
          _error = 'Rejected: ${event.rejectionCode}';
        }
      });
      _uid.clear();
    } on NoActiveSectionError {
      setState(() => _error = 'No active class section.');
    } catch (_) {
      setState(() => _error = 'Scan failed.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('NFC · ${widget.clazz.displayLabel}')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _booting
            ? const Center(child: CircularProgressIndicator())
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Enter card UID (platform NFC adapter can replace this field).'),
                  TextField(
                    controller: _uid,
                    decoration: const InputDecoration(labelText: 'HF card UID'),
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
