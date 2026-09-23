import 'package:flutter/material.dart';

import '../app/admin_app_controller.dart';
import 'admin_widgets.dart';

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
  bool _obscurePassword = true;

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
    if (_submitting) return;
    FocusScope.of(context).unfocus();
    setState(() => _submitting = true);
    await widget.controller.login(_identifier.text.trim(), _password.text);
    if (mounted) setState(() => _submitting = false);
  }

  Future<void> _verifyMfa() async {
    if (_submitting) return;
    FocusScope.of(context).unfocus();
    setState(() => _submitting = true);
    await widget.controller.submitMfa(_mfaCode.text);
    if (mounted) setState(() => _submitting = false);
  }

  Widget _spinner() => const SizedBox(
        height: 20,
        width: 20,
        child: CircularProgressIndicator(strokeWidth: 2),
      );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final mfaStep = widget.controller.pendingMfaToken != null;
    final error = widget.controller.errorMessage;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 16),
                  const Center(child: BrandMark(icon: Icons.admin_panel_settings)),
                  const SizedBox(height: 20),
                  Text(
                    'SchoolPass',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Admin',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    mfaStep
                        ? 'Enter the code from your authenticator app to finish signing in.'
                        : 'Manage people, classes, buses and imports for your school.',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 32),
                  if (!mfaStep) ...[
                    TextField(
                      controller: _identifier,
                      decoration: const InputDecoration(
                        labelText: 'Email or phone',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.username],
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _password,
                      decoration: InputDecoration(
                        labelText: 'Password',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          tooltip: _obscurePassword ? 'Show password' : 'Hide password',
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                          onPressed: () =>
                              setState(() => _obscurePassword = !_obscurePassword),
                        ),
                      ),
                      obscureText: _obscurePassword,
                      autofillHints: const [AutofillHints.password],
                      onSubmitted: (_) => _login(),
                    ),
                  ] else ...[
                    const Center(child: BrandMark(icon: Icons.shield_outlined, size: 56)),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _mfaCode,
                      decoration: const InputDecoration(
                        labelText: 'Authenticator code',
                        prefixIcon: Icon(Icons.pin_outlined),
                      ),
                      keyboardType: TextInputType.number,
                      onSubmitted: (_) => _verifyMfa(),
                    ),
                  ],
                  if (error != null) ...[
                    const SizedBox(height: 12),
                    ErrorBanner(message: error),
                  ],
                  const SizedBox(height: 24),
                  if (!mfaStep)
                    FilledButton(
                      onPressed: _submitting ? null : _login,
                      child: _submitting ? _spinner() : const Text('Sign in'),
                    )
                  else ...[
                    FilledButton(
                      onPressed: _submitting ? null : _verifyMfa,
                      child: _submitting ? _spinner() : const Text('Verify'),
                    ),
                    TextButton(
                      onPressed: _submitting ? null : widget.controller.cancelMfa,
                      child: const Text('Back to sign in'),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Text(
                    'Sign in with your school administrator account.',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
