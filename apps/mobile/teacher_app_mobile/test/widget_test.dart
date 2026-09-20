import 'package:flutter_test/flutter_test.dart';
import 'package:teacher_app/teacher_app.dart';

void main() {
  testWidgets('shows sign-in when no session', (WidgetTester tester) async {
    final deps = TeacherDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: InMemoryTokenStore(),
    );
    await tester.pumpWidget(TeacherAppShell(deps: deps));
    await tester.pumpAndSettle();
    expect(find.textContaining('Sign in'), findsOneWidget);
  });
}
