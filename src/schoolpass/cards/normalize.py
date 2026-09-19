"""Deterministic identifier normalization at persistence/search boundaries."""

from __future__ import annotations


def normalize_hf_uid(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_uhf_epc(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


def normalize_uhf_tid(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None
