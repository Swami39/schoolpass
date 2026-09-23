"""On-prem edge agent for UHF gate readers.

Runs on a small box on the school LAN next to the reader(s). It speaks the
reader's native protocol, converts tag sightings into SchoolPass canonical
RFID events, and POSTs them to ``/ingest/v1/rfid/events`` with HMAC device
authentication.

A local SQLite outbox makes delivery durable: an event is persisted
before its first POST attempt and retried with the *same*
``device_event_id`` (fresh nonce per attempt) until the server accepts it.

Run: ``python -m schoolpass.edge_agent`` (configuration via environment).
"""
