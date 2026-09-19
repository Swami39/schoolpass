import 'package:flutter/material.dart';

import '../academic/admin_academic_api.dart';
import '../app/admin_dependencies.dart';

class AcademicListScreen<T> extends StatefulWidget {
  const AcademicListScreen({
    required this.title,
    required this.deps,
    required this.loader,
    required this.label,
    super.key,
  });

  final String title;
  final AdminDependencies deps;
  final Future<List<T>> Function() loader;
  final String Function(T item) label;

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: _loading
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
                  ? const Center(child: Text('No records yet.'))
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        itemCount: _items.length,
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          return ListTile(title: Text(widget.label(item)));
                        },
                      ),
                    ),
    );
  }
}
