"""Vendor-specific UHF reader protocol adapters.

Each module here speaks one reader family's wire protocol and converts it
into SchoolPass canonical RFID events. Canonical JSON is the only thing
that ever reaches ``POST /ingest/v1/rfid/events``.
"""
