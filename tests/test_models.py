"""Tests for models.py — compute_validity_label."""

from __future__ import annotations

from datetime import date

from tkdn_finder.models import CertificateRow, compute_validity_label

TODAY = date(2026, 6, 25)


def _cert(**kwargs: object) -> CertificateRow:
    base: dict[str, object] = {
        "id": 1,
        "nama_perusahaan": "PT Test Corp",
        "nama_produk": "Gate Valve",
        "spesifikasi": "6 inch",
    }
    base.update(kwargs)
    return CertificateRow(**base)  # type: ignore[arg-type]


class TestValidityLabelWithMasaBerlaku:
    def test_future_date_beyond_window_is_valid(self) -> None:
        cert = _cert(masa_berlaku_akhir=date(2027, 12, 31))
        assert compute_validity_label(cert, TODAY) == "valid"

    def test_within_expiring_window_is_expiring(self) -> None:
        cert = _cert(masa_berlaku_akhir=date(2026, 8, 1))
        assert compute_validity_label(cert, TODAY) == "expiring"

    def test_past_date_is_expired(self) -> None:
        cert = _cert(masa_berlaku_akhir=date(2026, 1, 1))
        assert compute_validity_label(cert, TODAY) == "expired"


class TestValidityLabelP3dnTracking:
    def test_seen_today_with_no_not_found_marker_is_active(self) -> None:
        cert = _cert(p3dn_search_last_seen=TODAY, p3dn_not_found_since=None)
        assert compute_validity_label(cert, TODAY) == "p3dn_active"

    def test_seen_on_a_prior_scrape_day_is_still_active(self) -> None:
        """A record found on the last scrape stays 'active' on later days too —
        the day gap alone must not flip it to 'not found'."""
        cert = _cert(
            p3dn_search_last_seen=date(2026, 6, 20),
            p3dn_not_found_since=None,
        )
        assert compute_validity_label(cert, TODAY) == "p3dn_active"

    def test_not_found_since_set_overrides_last_seen(self) -> None:
        cert = _cert(
            p3dn_search_last_seen=date(2026, 6, 1),
            p3dn_not_found_since=date(2026, 6, 20),
        )
        assert compute_validity_label(cert, TODAY) == "p3dn_not_found"

    def test_no_p3dn_tracking_data_is_unknown(self) -> None:
        cert = _cert()
        assert compute_validity_label(cert, TODAY) == "unknown"
