import 'package:flutter/material.dart';
import 'package:parent_bus_location_ui/parent_bus_location_ui.dart';

import '../app/parent_app_controller.dart';

class BusScreen extends StatelessWidget {
  const BusScreen({required this.controller, required this.studentId, super.key});

  final ParentAppController controller;
  final String studentId;

  @override
  Widget build(BuildContext context) {
    return ParentBusLocationScreen.withApi(
      studentId: studentId,
      api: controller.deps.busLocationApi,
      onAuthFailure: (_) {
        controller.logout();
      },
    );
  }
}
