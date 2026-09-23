import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;

/// Configuration for push notification setup in a SchoolPass app.
class PushSetup {
  PushSetup({
    required this.getAuthToken,
    required this.apiBaseUrl,
    required this.appLabel,
  });

  /// Returns the current bearer auth token, or null when not signed in.
  /// Registration is skipped while this returns null.
  final Future<String?> Function() getAuthToken;

  /// API origin with no trailing slash, e.g. 'http://127.0.0.1:8000'.
  final String apiBaseUrl;

  /// One of 'admin', 'parent', 'teacher', 'attendant'.
  final String appLabel;
}

const String _androidChannelId = 'schoolpass_push';
const String _androidChannelName = 'SchoolPass notifications';
const String _androidChannelDescription = 'SchoolPass push notifications';

AndroidNotificationChannel _pushChannel() => const AndroidNotificationChannel(
      _androidChannelId,
      _androidChannelName,
      description: _androidChannelDescription,
      importance: Importance.high,
    );

NotificationDetails _notificationDetails() => const NotificationDetails(
      android: AndroidNotificationDetails(
        _androidChannelId,
        _androidChannelName,
        channelDescription: _androidChannelDescription,
        importance: Importance.high,
        priority: Priority.high,
      ),
      iOS: DarwinNotificationDetails(),
    );

InitializationSettings _initSettings() => const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      iOS: DarwinInitializationSettings(),
    );

/// Builds an initialized [FlutterLocalNotificationsPlugin] and ensures the
/// SchoolPass notification channel exists on Android.
Future<FlutterLocalNotificationsPlugin> _initLocalNotifications() async {
  final plugin = FlutterLocalNotificationsPlugin();
  await plugin.initialize(
    _initSettings(),
    onDidReceiveNotificationResponse: (NotificationResponse response) {
      debugPrint(
          'mobile_push: notification tapped (payload=${response.payload})');
    },
  );
  final android = plugin.resolvePlatformSpecificImplementation<
      AndroidFlutterLocalNotificationsPlugin>();
  await android?.createNotificationChannel(_pushChannel());
  return plugin;
}

/// Displays a push [message] as a local notification. Never throws.
Future<void> _showNotification(RemoteMessage message) async {
  try {
    final plugin = await _initLocalNotifications();
    final title = message.notification?.title ?? 'SchoolPass';
    final body = message.notification?.body ?? '';
    final id = message.messageId?.hashCode ?? 0;
    final rawPayload = message.data['notification_id'];
    final payload = rawPayload == null ? null : '$rawPayload';
    await plugin.show(
      id,
      title,
      body,
      _notificationDetails(),
      payload: payload,
    );
  } catch (e) {
    debugPrint('mobile_push: failed to show notification: $e');
  }
}

/// Background/terminated push handler. Must stay a top-level function so the
/// Firebase Messaging background isolate can invoke it.
@pragma('vm:entry-point')
Future<void> pushBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
    await _showNotification(message);
  } catch (e) {
    debugPrint('mobile_push: background handler failed: $e');
  }
}

/// Initializes FCM for the app and registers the device token with the
/// SchoolPass API. Never throws: every step is guarded so push can never
/// break app startup.
Future<void> initPush(PushSetup setup) async {
  try {
    await Firebase.initializeApp();
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission(alert: true, badge: true, sound: true);
    await messaging.setForegroundNotificationPresentationOptions(
      alert: true,
      badge: true,
      sound: true,
    );
    FirebaseMessaging.onBackgroundMessage(pushBackgroundHandler);

    final plugin = await _initLocalNotifications();
    // Android 13+ requires a runtime grant before notifications can post.
    if (Platform.isAndroid) {
      await plugin
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
    }

    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      unawaited(_showNotification(message));
    });
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      debugPrint(
          'mobile_push: notification opened app (messageId=${message.messageId})');
    });

    final token = await messaging.getToken();
    if (token != null && token.isNotEmpty) {
      await registerPushToken(setup, token);
    }
    messaging.onTokenRefresh.listen((String token) {
      unawaited(registerPushToken(setup, token));
    });
  } catch (e) {
    debugPrint('mobile_push: initPush failed: $e');
  }
}

/// Returns the current FCM registration token, or null when unavailable.
/// Never throws.
Future<String?> currentFcmToken() async {
  try {
    return await FirebaseMessaging.instance.getToken();
  } catch (_) {
    return null;
  }
}

Uri _deviceTokensUri(PushSetup setup, [Map<String, String>? queryParameters]) {
  final base = setup.apiBaseUrl.endsWith('/')
      ? setup.apiBaseUrl.substring(0, setup.apiBaseUrl.length - 1)
      : setup.apiBaseUrl;
  return Uri.parse('$base/api/v1/push/device-tokens')
      .replace(queryParameters: queryParameters);
}

String _platformName() {
  if (Platform.isAndroid) return 'android';
  if (Platform.isIOS) return 'ios';
  return 'unknown';
}

/// Registers [fcmToken] with the SchoolPass push endpoint.
/// Returns true on a 2xx response, false otherwise. Never throws.
/// Skipped (returns false) when there is no auth token yet.
Future<bool> registerPushToken(PushSetup setup, String fcmToken) async {
  try {
    if (fcmToken.isEmpty) return false;
    final authToken = await setup.getAuthToken();
    if (authToken == null || authToken.isEmpty) return false;
    final response = await http.post(
      _deviceTokensUri(setup),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $authToken',
      },
      body: jsonEncode(<String, String>{
        'fcm_token': fcmToken,
        'platform': _platformName(),
        'app_label': setup.appLabel,
      }),
    );
    return response.statusCode >= 200 && response.statusCode < 300;
  } catch (_) {
    return false;
  }
}

/// Unregisters the current device token from the SchoolPass push endpoint.
/// Returns true on a 2xx response, false otherwise. Never throws.
/// Must be called BEFORE logout clears the auth token.
Future<bool> unregisterPushToken(PushSetup setup) async {
  try {
    final authToken = await setup.getAuthToken();
    if (authToken == null || authToken.isEmpty) return false;
    final fcmToken = await currentFcmToken();
    if (fcmToken == null || fcmToken.isEmpty) return false;
    final response = await http.delete(
      _deviceTokensUri(setup, <String, String>{'fcm_token': fcmToken}),
      headers: <String, String>{
        'Authorization': 'Bearer $authToken',
      },
    );
    return response.statusCode >= 200 && response.statusCode < 300;
  } catch (_) {
    return false;
  }
}
