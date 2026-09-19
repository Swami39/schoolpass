/// Active class section for teacher NFC scans.
class SectionContext {
  String? get currentSectionId => _sectionId;
  String? _sectionId;

  void setSection(String sectionId) {
    _sectionId = sectionId;
  }

  void clear() {
    _sectionId = null;
  }
}
