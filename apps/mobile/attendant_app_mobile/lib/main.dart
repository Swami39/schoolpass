import 'dart:async';

import 'package:attendant_app/attendant_app.dart';
import 'package:attendant_secure_storage/attendant_secure_storage.dart';
import 'package:flutter/material.dart';
import 'package:mobile_push/mobile_push.dart';

void main() {
  final deps = AttendantDependencies.create(
    apiOrigin: Uri.parse(
      const String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://127.0.0.1:8000'),
    ),
    tokenStore: createProductionTokenStore(),
  );
  // Start FCM push. initPush never throws, so this cannot break startup.
  // Registration is retried after login when no auth token exists yet.
  unawaited(initPush(PushSetup(
    getAuthToken: deps.tokenStore.readAccessToken,
    apiBaseUrl: deps.apiOrigin.toString(),
    appLabel: 'attendant',
  )));
  runApp(AttendantAppShell(deps: deps));
}
