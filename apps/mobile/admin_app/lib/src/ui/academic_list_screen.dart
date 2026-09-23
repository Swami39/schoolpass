import 'package:flutter/material.dart';

import '../academic/admin_academic_api.dart';
import '../app/admin_dependencies.dart';
import 'admin_widgets.dart';

class AcademicListScreen<T> extends StatefulWidget {
  const AcademicListScreen({
    required this.title,
    required this.deps,
    required this.loader,
    required this.label,
    this.onCreate,
    this.subtitle,
    super.key,
  });

  final String title;
  final AdminDependencies deps;
  final Future<List<T>> Function() loader;
  final String Function(T item) label;
  final String Function(T item)? subtitle;
  final Future<void> Function()? onCreate;

  @override
  State<AcademicListScreen<T>> createState() => _AcademicListScreenState<T>();
}

class _AcademicListScreenState<T> extends State<AcademicListScreen<T>> {
  List<T> _items = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      _items = await widget.loader();
    } on AdminAcademicUnauthorized {
      _error = 'Session expired. Sign in again from the menu.';
    } on AdminAcademicApiFailure catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load data.';
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _create() async {
    final create = widget.onCreate;
    if (create == null) return;
    await create();
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          if (widget.onCreate != null)
            IconButton(
              onPressed: _create,
              icon: const Icon(Icons.add),
              tooltip: 'Create',
            ),
        ],
      ),
      floatingActionButton: widget.onCreate == null
          ? null
          : FloatingActionButton.extended(
              onPressed: _create,
              icon: const Icon(Icons.add),
              label: const Text('Add'),
            ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorRetry(message: _error!, onRetry: _load)
              : _items.isEmpty
                  ? EmptyState(
                      icon: Icons.menu_book_outlined,
                      title: 'No ${widget.title.toLowerCase()} yet',
                      subtitle: widget.onCreate != null
                          ? 'Create the first one to get started.'
                          : null,
                      actionLabel: widget.onCreate != null ? 'Create' : null,
                      onAction: widget.onCreate != null ? _create : null,
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                        itemCount: _items.length,
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          final subtitle = widget.subtitle?.call(item);
                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              title: Text(widget.label(item)),
                              subtitle: subtitle == null ? null : Text(subtitle),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
