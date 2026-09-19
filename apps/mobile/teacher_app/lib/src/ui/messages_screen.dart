import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';

class MessagesScreen extends StatefulWidget {
  const MessagesScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  bool _urgent = false;
  bool _sending = false;
  String? _error;
  List<TeacherStudent> _students = const [];
  TeacherStudent? _target;

  @override
  void initState() {
    super.initState();
    _loadStudents();
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _loadStudents() async {
    try {
      final items = await widget.controller.deps.classesApi.fetchStudents(widget.clazz.sectionId);
      if (!mounted) return;
      setState(() => _students = items);
    } catch (_) {
      // Class message still allowed without student list.
    }
  }

  Future<void> _send() async {
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final result = await widget.controller.deps.messagesApi.sendMessage(
        sectionId: widget.clazz.sectionId,
        title: _title.text.trim(),
        body: _body.text.trim(),
        idempotencyKey: const Uuid().v4(),
        studentId: _target?.id,
        urgent: _urgent,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sent to ${result.recipientCount} guardian(s)')),
      );
      _title.clear();
      _body.clear();
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } on TeacherNotFound {
      setState(() => _error = 'Not authorized for this class or student.');
    } catch (_) {
      setState(() => _error = 'Message failed to send.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Message · ${widget.clazz.displayLabel}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          DropdownButtonFormField<TeacherStudent?>(
            // ignore: deprecated_member_use
            value: _target,
            decoration: const InputDecoration(labelText: 'Recipient'),
            items: [
              const DropdownMenuItem(value: null, child: Text('Entire class')),
              for (final s in _students)
                DropdownMenuItem(value: s, child: Text(s.displayName)),
            ],
            onChanged: (v) => setState(() => _target = v),
          ),
          TextField(controller: _title, decoration: const InputDecoration(labelText: 'Title')),
          TextField(
            controller: _body,
            decoration: const InputDecoration(labelText: 'Message'),
            maxLines: 4,
          ),
          SwitchListTile(
            title: const Text('Urgent'),
            value: _urgent,
            onChanged: (v) => setState(() => _urgent = v),
          ),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          FilledButton(
            onPressed: _sending ? null : _send,
            child: _sending
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Send'),
          ),
        ],
      ),
    );
  }
}
