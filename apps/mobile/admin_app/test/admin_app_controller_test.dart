import 'package:admin_app/src/app/admin_app_controller.dart';
import 'package:admin_app/src/app/admin_dependencies.dart';
import 'package:admin_app/src/session/token_store.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('bootstrap signed out when no session', () async {
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: InMemoryTokenStore(),
    );
    final controller = AdminAppController(deps);
    await controller.bootstrap();
    expect(controller.phase, AdminAppPhase.signedOut);
  });
}
