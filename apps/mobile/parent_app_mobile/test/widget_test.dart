import 'package:flutter_test/flutter_test.dart';
import 'package:parent_app/parent_app.dart';

void main() {
  testWidgets('shows sign-in when no session', (WidgetTester tester) async {
    final deps = ParentDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: InMemoryTokenStore(),
      pushProvider: FakePlatformPushProvider(),
    );
    await tester.pumpWidget(ParentAppShell(deps: deps));
    await tester.pumpAndSettle();
    expect(find.textContaining('Sign in'), findsOneWidget);
  });
}
