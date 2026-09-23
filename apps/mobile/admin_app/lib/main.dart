import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mobile_push/mobile_push.dart';

import 'src/app/admin_app_shell.dart';
import 'src/app/admin_dependencies.dart';

void main() {
  final deps = AdminDependencies.production();
  // Start FCM push. initPush never throws, so this cannot break startup.
  // Registration is retried after login when no auth token exists yet.
  // Note: the admin app currently uses an in-memory token store, so push
  // registration only happens after a successful login.
  unawaited(initPush(PushSetup(
    getAuthToken: deps.tokenStore.readAccessToken,
    apiBaseUrl: deps.apiOrigin.toString(),
    appLabel: 'admin',
  )));
  runApp(AdminAppShell(deps: deps));
}
