import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';

typedef PeopleLoader<T> = Future<List<T>> Function({String? search, String? filter});

class PeopleListScreen<T> extends StatefulWidget {
  const PeopleListScreen({
    required this.title,
    required this.deps,
    required this.loader,
    required this.label,
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
          padding: const EdgeInsets.all(8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: 'Search',
                    suffixIcon: IconButton(icon: const Icon(Icons.search), onPressed: _load),
                  ),
                  onSubmitted: (_) => _load(),
                ),
              ),
              if (widget.filterOptions != null && widget.filterOptions!.isNotEmpty)
                DropdownButton<String>(
                  value: _filter,
                  hint: const Text('Filter'),
                  items: widget.filterOptions!
                      .map((f) => DropdownMenuItem(value: f, child: Text(f)))
                      .toList(),
                  onChanged: (v) {
                    setState(() => _filter = v);
                    _load();
                  },
                ),
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(_error!, textAlign: TextAlign.center),
                          const SizedBox(height: 12),
                          FilledButton(onPressed: _load, child: const Text('Retry')),
                        ],
                      ),
                    )
                  : _items.isEmpty
                      ? const Center(child: Text('No records found.'))
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView.builder(
                            itemCount: _items.length,
                            itemBuilder: (context, index) {
                              final item = _items[index];
                              return ListTile(
                                title: Text(widget.label(item)),
                                onTap: widget.onTap == null ? null : () => widget.onTap!(item),
                              );
                            },
                          ),
                        ),
        ),
      ],
    );
    final fab = widget.onCreate == null
        ? null
        : FloatingActionButton(onPressed: widget.onCreate, child: const Icon(Icons.add));
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
