import 'package:admin_app/src/app/admin_app_shell.dart';
import 'package:admin_app/src/app/admin_dependencies.dart';
import 'package:admin_app/src/session/token_store.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows sign-in when no session', (WidgetTester tester) async {
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: InMemoryTokenStore(),
    );
    await tester.pumpWidget(AdminAppShell(deps: deps));
    await tester.pumpAndSettle();
    expect(find.textContaining('Sign in'), findsOneWidget);
  });
}
