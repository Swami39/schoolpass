import 'package:flutter/material.dart';

import '../app/admin_app_controller.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({required this.controller, super.key});

  final AdminAppController controller;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _identifier = TextEditingController();
  final _password = TextEditingController();
  final _mfaCode = TextEditingController();
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    const email = String.fromEnvironment('SCHOOLPASS_DEBUG_EMAIL');
    const password = String.fromEnvironment('SCHOOLPASS_DEBUG_PASSWORD');
    if (email.isNotEmpty) {
      _identifier.text = email;
    }
    if (password.isNotEmpty) {
      _password.text = password;
    }
    const autoSignIn = bool.fromEnvironment('SCHOOLPASS_DEBUG_AUTOSIGNIN');
    if (autoSignIn && email.isNotEmpty && password.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !_submitting) {
          _login();
        }
      });
    }
  }

  @override
  void dispose() {
    _identifier.dispose();
    _password.dispose();
    _mfaCode.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() => _submitting = true);
    await widget.controller.login(_identifier.text.trim(), _password.text);
    if (mounted) setState(() => _submitting = false);
  }

  Future<void> _verifyMfa() async {
    setState(() => _submitting = true);
    await widget.controller.submitMfa(_mfaCode.text);
    if (mounted) setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    final mfaStep = widget.controller.pendingMfaToken != null;
    return Scaffold(
      appBar: AppBar(title: const Text('SchoolPass Admin')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (!mfaStep) ...[
                TextField(
                  controller: _identifier,
                  decoration: const InputDecoration(labelText: 'Email or phone'),
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.username],
                  textInputAction: TextInputAction.next,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  decoration: const InputDecoration(labelText: 'Password'),
                  obscureText: true,
                  autofillHints: const [AutofillHints.password],
                  onSubmitted: (_) => _submitting ? null : _login(),
                ),
              ] else ...[
                const Text('Enter the code from your authenticator app.'),
                const SizedBox(height: 12),
                TextField(
                  controller: _mfaCode,
                  decoration: const InputDecoration(labelText: 'MFA code'),
                  keyboardType: TextInputType.number,
                  onSubmitted: (_) => _submitting ? null : _verifyMfa(),
                ),
              ],
              if (widget.controller.errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  widget.controller.errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 24),
              if (!mfaStep)
                FilledButton(
                  onPressed: _submitting ? null : _login,
                  child: _submitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Sign in'),
                )
              else ...[
                FilledButton(
                  onPressed: _submitting ? null : _verifyMfa,
                  child: _submitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Verify MFA'),
                ),
                TextButton(
                  onPressed: widget.controller.cancelMfa,
                  child: const Text('Back'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
