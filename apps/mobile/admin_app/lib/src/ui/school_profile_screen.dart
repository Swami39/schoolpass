import 'package:flutter/material.dart';

import '../app/admin_app_controller.dart';

class SchoolProfileScreen extends StatefulWidget {
  const SchoolProfileScreen({required this.controller, super.key});

  final AdminAppController controller;

  @override
  State<SchoolProfileScreen> createState() => _SchoolProfileScreenState();
}

class _SchoolProfileScreenState extends State<SchoolProfileScreen> {
  final _legalName = TextEditingController();
  final _displayName = TextEditingController();
  final _timezone = TextEditingController();
  final _country = TextEditingController();
  final _contactEmail = TextEditingController();
  final _contactPhone = TextEditingController();
  final _address = TextEditingController();
  final _city = TextEditingController();
  final _state = TextEditingController();
  final _postal = TextEditingController();
  bool _hydrated = false;

  @override
  void initState() {
    super.initState();
    // Defer so notifyListeners does not run while the parent AnimatedBuilder is building.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.controller.loadSchoolProfile();
    });
  }

  @override
  void dispose() {
    _legalName.dispose();
    _displayName.dispose();
    _timezone.dispose();
    _country.dispose();
    _contactEmail.dispose();
    _contactPhone.dispose();
    _address.dispose();
    _city.dispose();
    _state.dispose();
    _postal.dispose();
    super.dispose();
  }

  void _hydrateFromProfile() {
    final profile = widget.controller.schoolProfile;
    if (profile == null || _hydrated) return;
    _legalName.text = profile.legalName;
    _displayName.text = profile.displayName ?? '';
    _timezone.text = profile.timezone;
    _country.text = profile.country;
    _contactEmail.text = profile.contactEmail ?? '';
    _contactPhone.text = profile.contactPhone ?? '';
    _address.text = profile.addressLine1 ?? '';
    _city.text = profile.city ?? '';
    _state.text = profile.state ?? '';
    _postal.text = profile.postalCode ?? '';
    _hydrated = true;
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        if (widget.controller.loadingProfile && widget.controller.schoolProfile == null) {
          return const Center(child: CircularProgressIndicator());
        }
        _hydrateFromProfile();
        return ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (widget.controller.errorMessage != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  widget.controller.errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (widget.controller.successMessage != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  widget.controller.successMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.primary),
                ),
              ),
            if (widget.controller.schoolProfile?.logoFileId != null)
              ListTile(
                leading: const Icon(Icons.image_outlined),
                title: const Text('School logo'),
                subtitle: Text('File ${widget.controller.schoolProfile!.logoFileId}'),
              ),
            TextField(
              controller: _legalName,
              decoration: const InputDecoration(labelText: 'Legal name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _displayName,
              decoration: const InputDecoration(labelText: 'Display name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _timezone,
              decoration: const InputDecoration(labelText: 'Timezone'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _country,
              decoration: const InputDecoration(labelText: 'Country (ISO code)'),
              maxLength: 2,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _contactEmail,
              decoration: const InputDecoration(labelText: 'Contact email'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _contactPhone,
              decoration: const InputDecoration(labelText: 'Contact phone'),
              keyboardType: TextInputType.phone,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _address,
              decoration: const InputDecoration(labelText: 'Address'),
            ),
            const SizedBox(height: 12),
            TextField(controller: _city, decoration: const InputDecoration(labelText: 'City')),
            const SizedBox(height: 12),
            TextField(controller: _state, decoration: const InputDecoration(labelText: 'State')),
            const SizedBox(height: 12),
            TextField(
              controller: _postal,
              decoration: const InputDecoration(labelText: 'Postal code'),
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: widget.controller.savingProfile
                  ? null
                  : () async {
                      _hydrated = false;
                      await widget.controller.saveSchoolProfile(
                        legalName: _legalName.text.trim(),
                        displayName: _displayName.text.trim().isEmpty ? null : _displayName.text.trim(),
                        timezone: _timezone.text.trim(),
                        country: _country.text.trim().toUpperCase(),
                        contactEmail:
                            _contactEmail.text.trim().isEmpty ? null : _contactEmail.text.trim(),
                        contactPhone:
                            _contactPhone.text.trim().isEmpty ? null : _contactPhone.text.trim(),
                        addressLine1: _address.text.trim().isEmpty ? null : _address.text.trim(),
                        city: _city.text.trim().isEmpty ? null : _city.text.trim(),
                        state: _state.text.trim().isEmpty ? null : _state.text.trim(),
                        postalCode: _postal.text.trim().isEmpty ? null : _postal.text.trim(),
                      );
                    },
              child: widget.controller.savingProfile
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save profile'),
            ),
          ],
        );
      },
    );
  }
}
