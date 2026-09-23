import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import 'admin_widgets.dart';
import 'format.dart';

typedef PeopleLoader<T> = Future<List<T>> Function({String? search, String? filter});

class PeopleListScreen<T> extends StatefulWidget {
  const PeopleListScreen({
    required this.title,
    required this.deps,
    required this.loader,
    required this.label,
    this.subtitle,
    this.onTap,
    this.filterOptions,
    this.onCreate,
    this.useScaffold = true,
    super.key,
  });

  final String title;
  final AdminDependencies deps;
  final PeopleLoader<T> loader;
  final String Function(T item) label;
  final String Function(T item)? subtitle;
  final void Function(T item)? onTap;
  final List<String>? filterOptions;
  final VoidCallback? onCreate;
  final bool useScaffold;

  @override
  State<PeopleListScreen<T>> createState() => _PeopleListScreenState<T>();
}

class _PeopleListScreenState<T> extends State<PeopleListScreen<T>> {
  List<T> _items = const [];
  bool _loading = true;
  String? _error;
  final _searchCtrl = TextEditingController();
  String? _filter;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      _items = await widget.loader(search: _searchCtrl.text.trim(), filter: _filter);
    } on AdminPeopleUnauthorized {
      _error = 'Session expired. Sign in again.';
    } on AdminPeopleApiFailure catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load data.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: 'Search ${widget.title.toLowerCase()}…',
                    prefixIcon: const Icon(Icons.search),
                  ),
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) => _load(),
                ),
              ),
              if (widget.filterOptions != null && widget.filterOptions!.isNotEmpty) ...[
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _filter,
                  hint: const Text('Filter'),
                  underline: const SizedBox.shrink(),
                  items: [
                    const DropdownMenuItem<String>(
                      value: null,
                      child: Text('All'),
                    ),
                    ...widget.filterOptions!.map(
                      (f) => DropdownMenuItem(value: f, child: Text(prettifyLabel(f))),
                    ),
                  ],
                  onChanged: (v) {
                    setState(() => _filter = v);
                    _load();
                  },
                ),
              ],
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? ErrorRetry(message: _error!, onRetry: _load)
                  : _items.isEmpty
                      ? EmptyState(
                          icon: Icons.people_outline,
                          title: 'No ${widget.title.toLowerCase()} found',
                          subtitle: widget.onCreate != null
                              ? 'Try a different search, or add a new record.'
                              : 'Try a different search.',
                          actionLabel: widget.onCreate != null ? 'Add new' : null,
                          onAction: widget.onCreate,
                        )
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                            itemCount: _items.length,
                            itemBuilder: (context, index) {
                              final item = _items[index];
                              final subtitle = widget.subtitle?.call(item);
                              return Card(
                                margin: const EdgeInsets.only(bottom: 8),
                                child: ListTile(
                                  title: Text(widget.label(item)),
                                  subtitle: subtitle == null ? null : Text(subtitle),
                                  trailing: widget.onTap == null
                                      ? null
                                      : const Icon(Icons.chevron_right),
                                  onTap: widget.onTap == null
                                      ? null
                                      : () => widget.onTap!(item),
                                ),
                              );
                            },
                          ),
                        ),
        ),
      ],
    );
    final fab = widget.onCreate == null
        ? null
        : FloatingActionButton.extended(
            onPressed: widget.onCreate,
            icon: const Icon(Icons.add),
            label: const Text('Add'),
          );
    if (!widget.useScaffold) {
      return Stack(
        children: [
          content,
          if (fab != null)
            Positioned(
              right: 16,
              bottom: 16,
              child: fab,
            ),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      floatingActionButton: fab,
      body: content,
    );
  }
}
