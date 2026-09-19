import 'package:flutter_test/flutter_test.dart';
import 'package:teacher_app/src/app/teacher_app_controller.dart';
import 'package:teacher_app/src/app/teacher_dependencies.dart';
import 'package:teacher_app/src/session/token_store.dart';

void main() {
  test('bootstrap signed out when no session', () async {
    final deps = TeacherDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: InMemoryTokenStore(),
    );
    final controller = TeacherAppController(deps);
    await controller.bootstrap();
    expect(controller.phase, TeacherAppPhase.signedOut);
  });
}
