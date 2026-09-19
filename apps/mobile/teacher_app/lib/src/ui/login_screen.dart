import 'package:flutter/material.dart';

import '../app/teacher_app_controller.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({required this.controller, super.key});

  final TeacherAppController controller;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _identifier = TextEditingController();
  final _password = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _identifier.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _submitting = true);
    await widget.controller.login(_identifier.text.trim(), _password.text);
    if (mounted) {
      setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final error = widget.controller.errorMessage;
    return Scaffold(
      appBar: AppBar(title: const Text('SchoolPass Teacher')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _identifier,
              decoration: const InputDecoration(labelText: 'Email or phone'),
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.username],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
              autofillHints: const [AutofillHints.password],
            ),
            if (error != null) ...[
              const SizedBox(height: 12),
              Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _submitting ? null : _submit,
              child: _submitting
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Sign in'),
            ),
          ],
        ),
      ),
    );
  }
}
