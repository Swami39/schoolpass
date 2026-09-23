# Push notifications (FCM)

## Why notifications were not reaching the phone tray

Until now SchoolPass had an **in-app** notification inbox only: the API was polled for new items, so nothing ever reached the Android/iOS notification tray. There was:

- no Firebase Cloud Messaging (FCM) sender on the backend,
- no device-token registration (except a parent-only route),
- no `firebase_messaging` in any app's `pubspec.yaml`.

That is now wired end to end. The backend sends real FCM HTTP v1 pushes; the four mobile apps register their FCM tokens after login and show foreground messages as local notifications.

## Architecture

```text
backend event -> Notification (inbox) + outbox row  (create_notification_with_outbox)
                    |
                    v  (worker loop)
          publish_outbox_batch -> Redis bus topic "notification.dispatch"
                    |
                    v
          process_notification_dispatch_batch -> NotificationDeliveryService
                    |  - checks NotificationPreference for the user
                    |  - lists active NotificationDevice rows for the user
                    |  - FcmHttpV1Provider.send_push(...) per device
                    v
          FCM HTTP v1 API  (HttpxFcmTransport, OAuth2 via service account)
                    |
                    v
          phone tray notification (+ data payload for in-app routing)
```

- **Token registry**: `notification_devices` table (`NotificationDevice`), extended with `app_label` (`admin`/`parent`/`teacher`/`attendant`) and `last_seen_at`.
- **Send path reuses the existing plumbing**: `NotificationDeliveryService` already checks preferences, fans out per device, and revokes devices when FCM reports `invalid_token`.
- **Disabled by default**: without `FCM_ENABLED=true` and a service-account key, the worker uses `DisabledFcmTransport` (safe no-op) and logs an `fcm_disabled` warning at startup.

## What was implemented (backend)

### New files

- `src/schoolpass/notifications/fcm_real.py`
  - `build_fcm_message(...)` — builds the FCM HTTP v1 `message` object: OS-renderable `notification` (title/body) + string-only `data` + `android.priority=HIGH` + APNs default sound. Data carries `notification_id` / `notification_type` for in-app routing.
  - `classify_fcm_response(...)` — maps FCM responses: `UNREGISTERED`/`INVALID_ARGUMENT` -> invalid token (device gets pruned); 429/5xx -> transient (delivery retries); 401/403 -> configuration error.
  - `GoogleServiceAccountCredentials` — mints OAuth2 access tokens from the service-account JSON key (`google-auth`), cached until shortly before expiry.
  - `HttpxFcmTransport` — delivers via `httpx` to `https://fcm.googleapis.com/v1/projects/{project_id}/messages:send`.
- `src/schoolpass/api/routes/push.py` — shared token API for all app roles:
  - `POST /api/v1/push/device-tokens` `{platform, fcm_token, app_label?}` — upserts the caller's token row (tenant + user scoped; a token registered to another user is rejected with 403).
  - `DELETE /api/v1/push/device-tokens?fcm_token=...` — revokes the caller's token (called on logout).
  - Guarded by role permissions `parent:push_register`, `teacher:push_register`, `bus_attendant:push_register`, `school_admin:push_register`.
- `alembic/versions/0017_push_device_app_label.py` — adds `app_label`/`last_seen_at` columns and seeds the three new `push_register` permissions + role assignments.
- `tests/test_push_fcm.py` — unit tests (`pytest -m unit`) for payload shape, response classification, and the transport (mocked `httpx`).

### Changed files

- `src/schoolpass/worker/main.py` — `_build_delivery_service()` now uses the real FCM transport when `fcm_enabled` and a service-account path are configured; keeps `RecordingFcmTransport` in tests and `DisabledFcmTransport` otherwise. Never logs tokens or secret paths.
- `src/schoolpass/config.py` — new settings `google_application_credentials` and `firebase_service_account_json`; property `fcm_service_account_path` prefers the Firebase-specific one.
- `src/schoolpass/notifications/models.py` — `NotificationDevice.app_label`, `NotificationDevice.last_seen_at`.
- `src/schoolpass/notifications/devices.py` — `register_fcm_device(..., app_label=...)` updates platform/label/last-seen on re-registration; race-safe upsert; new `unregister_fcm_device_by_token(...)` for logout.
- `src/schoolpass/notifications/schemas.py` — request/response carry `app_label`.
- `src/schoolpass/rbac/catalog.py` — new permissions `teacher:push_register`, `bus_attendant:push_register`, `school_admin:push_register` assigned to the matching roles (+ platform super admin).
- `src/schoolpass/api/main.py` — push router registered.
- `pyproject.toml` — production deps `google-auth>=2.30.0`, `httpx>=0.27.0`.
- `.env.example` — `FCM_ENABLED`, `FCM_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`.

### Mobile apps (Flutter)

A shared `mobile_push` package wraps `firebase_messaging` + `flutter_local_notifications`:

- `initPush(...)` — initializes Firebase, requests notification permission, registers the background handler, creates the Android notification channel (Android 8+), requests Android 13+ runtime permission.
- `registerPushToken(...)` — POSTs the FCM token to `/api/v1/push/device-tokens` with the app's `app_label`.
- `unregisterPushToken(...)` — DELETEs the token on logout.
- `pushBackgroundHandler` (top-level `@pragma('vm:entry-point')`) — handles taps/processing when the app is terminated.
- Foreground messages are shown through `flutter_local_notifications` so a banner appears even while the app is open.
- Init is defensive: if Firebase/config/network is unavailable, app startup is never broken.

Each of the four apps (`admin_app`, `parent_app`, `teacher_app`, `attendant_app`) depends on `../mobile_push`, calls `initPush` at startup with its API base URL + auth-token getter, registers the token after login, and unregisters on logout with its own `app_label` (`admin`, `parent`, `teacher`, `attendant`).

Android: the Google Services Gradle plugin (4.4.2) is applied in each `*_app_mobile` shell's `android/` project. **Applying the plugin makes APK builds fail with a clear "google-services.json missing" error until you place the file** — that is intentional, so a misconfigured build cannot silently ship without push.

## What you (the operator) must do

Code cannot create the Firebase project or download its credentials — do these once in the Firebase console (https://console.firebase.google.com):

### 1. Create the Firebase project

- Create a project (e.g. `schoolpass-push`). Google Analytics is optional.
- Note the **Project ID** — it becomes `FCM_PROJECT_ID`.

### 2. Register the four Android apps

In Project settings -> Your apps -> Add app -> Android, register each shell's **application ID** (one Firebase Android app per ID):

| App | Application ID | `google-services.json` goes to |
| --- | -------------- | ------------------------------- |
| Admin | `com.schoolpass.admin_app` | `apps/mobile/admin_app/android/app/` |
| Parent | `com.schoolpass.parent_app_mobile` | `apps/mobile/parent_app_mobile/android/app/` |
| Teacher | `com.schoolpass.teacher_app_mobile` | `apps/mobile/teacher_app_mobile/android/app/` |
| Attendant | `com.schoolpass.attendant_app_mobile` | `apps/mobile/attendant_app_mobile/android/app/` |

> ⚠️ Known issue: `attendant_app_mobile/android/app/build.gradle.kts` has `namespace = "com.schoolpass.teacher_app_mobile"` (copy-paste from cloning the teacher shell; `applicationId` is correct). Fixing the namespace requires renaming the Kotlin/Java package directories too — flagged for a follow-up with a compile check, not changed here.

### 3. Register the four iOS apps

Add app -> iOS for each shell's **bundle ID** and download each **`GoogleService-Info.plist`** into the matching Xcode Runner target:

| App | Bundle ID | iOS dir |
| --- | --------- | ------- |
| Admin | `com.schoolpass.adminApp` | `apps/mobile/admin_app/ios` |
| Parent | `com.schoolpass.parentAppMobile` | `apps/mobile/parent_app_mobile/ios` |
| Teacher | `com.schoolpass.teacherAppMobile` | `apps/mobile/teacher_app_mobile/ios` |
| Attendant | `com.schoolpass.teacherAppMobile` ⚠️ | `apps/mobile/attendant_app_mobile/ios` |

> ⚠️ **Must fix before Firebase iOS registration:** the attendant shell was cloned from the teacher shell and still uses bundle ID `com.schoolpass.teacherAppMobile`. Two apps cannot share a bundle ID — change the attendant's `PRODUCT_BUNDLE_IDENTIFIER` (e.g. to `com.schoolpass.attendantAppMobile`) in its `project.pbxproj` and Apple Developer portal before registering it in Firebase, or APNs pushes will misroute.

- In each iOS target enable **Push Notifications** and **Background Modes -> Remote notifications**.
- Upload an **APNs key** (Apple Developer -> Keys -> Apple Push Notifications service, download the `.p8`) in Firebase Project settings -> Cloud Messaging -> iOS app configuration. Without this, iOS devices get no pushes.

### 4. Create the backend service-account key

- Project settings -> Service accounts -> Generate new private key. This is the **server** credential the worker uses to call FCM.
- Save it **outside Git**, e.g. `~/Projects/schoolpass39/.data/firebase-service-account.json` (the `.data/` dir is git-ignored and mounted into containers at `/app/.data`).
- Never commit it, never paste it into chat.

### 5. Configure the environment

In `.env` (native run) and/or the Docker env:

```bash
FCM_ENABLED=true
FCM_PROJECT_ID=<your-firebase-project-id>
# native (scripts/run_api_lan.sh):
FIREBASE_SERVICE_ACCOUNT_JSON=/Users/swami/Projects/schoolpass39/.data/firebase-service-account.json
# docker (compose mounts ../../.data -> /app/.data):
FIREBASE_SERVICE_ACCOUNT_JSON=/app/.data/firebase-service-account.json
```

### 6. Migrate and rebuild

```bash
cd ~/Projects/schoolpass39
# DB migration (adds device columns + push permissions):
alembic upgrade head
# rebuild containers so the worker picks up google-auth/httpx:
docker compose -f infra/docker/compose.yaml up --build -d
```

### 7. Rebuild the mobile apps

After the `google-services.json` files are in place:

```bash
cd ~/Projects/schoolpass39
./scripts/build_android_physical_apks.sh
```

Install all four APKs, sign into each app, **grant the notification permission** when asked, then trigger a notification (e.g. a bus-boarding event or a manual test notification) and confirm:

- a tray notification appears with the app in background **and** fully killed;
- tapping it opens the app;
- the notification also appears in the app's in-app inbox.

## Verification commands

Backend unit tests (no DB needed):

```bash
cd ~/Projects/schoolpass39
pytest -m unit tests/test_push_fcm.py
```

Then, with PostgreSQL/Docker up: `alembic upgrade head` and the notification integration tests.

Each app (Flutter):

```bash
cd ~/Projects/schoolpass39/apps/mobile/admin_app && flutter pub get && flutter analyze
cd ~/Projects/schoolpass39/apps/mobile/parent_app && flutter pub get && flutter analyze
cd ~/Projects/schoolpass39/apps/mobile/teacher_app && flutter pub get && flutter analyze
cd ~/Projects/schoolpass39/apps/mobile/attendant_app && flutter pub get && flutter analyze
```

Quick API smoke test (after login, with a real JWT):

```bash
# register (expect 200 + the device row)
curl -X POST http://<api-host>:8000/api/v1/push/device-tokens \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"platform":"android","fcm_token":"<token>","app_label":"parent"}'
# unregister (expect {"revoked": true})
curl -X DELETE "http://<api-host>:8000/api/v1/push/device-tokens?fcm_token=<token>" \
  -H "Authorization: Bearer <JWT>"
```

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Worker logs `fcm_disabled` | `FCM_ENABLED` not true or key path unset | Set both env vars, restart worker |
| Worker logs `fcm_init_failed` | Key file missing/unreadable or wrong JSON | Check the path + file permissions |
| APK build fails: google-services.json missing | Expected — plugin applied, file not placed yet | Place the file per step 2, rebuild |
| Android tray notification missing, in-app shows | Token never registered (permission denied at OS level, or registration failed) | Grant notification permission; check app logs for the POST to `/api/v1/push/device-tokens` |
| iOS gets nothing, Android works | APNs key not uploaded in Firebase | Upload the `.p8` key, rebuild the iOS app |
| Token stops working after app reinstall | Expected — FCM issues a new token; the old row is pruned on the next `UNREGISTERED` response | Re-login re-registers automatically |
| 403 from `/api/v1/push/device-tokens` | Role lacks `push_register` (e.g. stale DB before migration 0017) | Run `alembic upgrade head` |

## Notes

- The older parent-only route `POST /api/v1/parent/push-devices` still exists and is kept for backward compatibility. New code uses the generic `/api/v1/push/device-tokens` (which adds `app_label`). A future cleanup can retire the parent-only route and the parent's legacy `PushNotificationService.registerDeviceIfNeeded()` call to it.
- Admin app note: `admin_app` has no `*_mobile` shell — its `android/`/`ios/` live directly under `apps/mobile/admin_app/`, and it uses an in-memory token store, so push registration is skipped until login completes (by design).

## Security notes

- FCM tokens are secrets: they are never logged, and the token API only ever returns them to the owning user/tenant.
- The service-account JSON is a powerful credential — keep it in `.data/`, never in Git, never in screenshots.
- Device rows are tenant-scoped by Postgres RLS like the rest of the notification domain.
