import 'dart:async';

import 'hf_uid.dart';

/// Normalized NFC scan from platform hardware (UID-only in Phase 6B.3).
class NfcScanResult {
  const NfcScanResult({required this.cardUid});

  final String cardUid;
}

/// Platform NFC is implemented behind this boundary (Flutter NFC plugin later).
abstract class NfcAdapter {
  Stream<NfcScanResult> get scans;
}

/// Test / integration stub: push scans programmatically.
class FakeNfcAdapter implements NfcAdapter {
  FakeNfcAdapter();

  final StreamController<NfcScanResult> _sink =
      StreamController<NfcScanResult>.broadcast();

  @override
  Stream<NfcScanResult> get scans => _sink.stream;

  void emitRawUid(String rawUid) {
    final normalized = normalizeHfUid(rawUid);
    if (normalized == null) {
      return;
    }
    _sink.add(NfcScanResult(cardUid: normalized));
  }

  void close() => _sink.close();
}
