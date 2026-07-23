"""Tests for models.py — compute_validity_label."""

from __future__ import annotations

from datetime import date, timedelta

from tkdn_finder.models import CertificateRow, compute_validity_label

TODAY = date(2026, 6, 25)
FUTURE = TODAY + timedelta(days=400)
PAST = TODAY - timedelta(days=10)


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
    def test_future_date_is_valid_when_web_presence_unknown(self) -> None:
        cert = _cert(masa_berlaku_akhir=FUTURE)
        assert compute_validity_label(cert, TODAY) == "valid"

    def test_past_date_is_not_valid_when_web_presence_unknown(self) -> None:
        cert = _cert(masa_berlaku_akhir=PAST)
        assert compute_validity_label(cert, TODAY) == "not_valid"


class TestValidityLabelCombinedWithWebPresence:
    """The 9-combination matrix: masa_berlaku_akhir (future/past/none) x
    P3DN web presence (present/lost/unscraped)."""

    def test_future_date_and_present_on_web_is_web_active(self) -> None:
        cert = _cert(masa_berlaku_akhir=FUTURE, p3dn_search_last_seen=TODAY)
        assert compute_validity_label(cert, TODAY) == "web_active"

    def test_future_date_and_lost_from_web_is_web_lost(self) -> None:
        """Still valid by date but no longer found on P3DN search.php —
        this combination used to be silently reported as 'valid'."""
        cert = _cert(
            masa_berlaku_akhir=FUTURE,
            p3dn_search_last_seen=PAST,
            p3dn_not_found_since=TODAY,
        )
        assert compute_validity_label(cert, TODAY) == "web_lost"

    def test_future_date_and_unscraped_is_valid(self) -> None:
        cert = _cert(masa_berlaku_akhir=FUTURE)
        assert compute_validity_label(cert, TODAY) == "valid"

    def test_past_date_and_present_on_web_is_expired_on_web(self) -> None:
        """Expired by date but still showing up on P3DN — surfaced for
        manual verification rather than trusting either signal alone."""
        cert = _cert(masa_berlaku_akhir=PAST, p3dn_search_last_seen=TODAY)
        assert compute_validity_label(cert, TODAY) == "expired_on_web"

    def test_past_date_and_lost_from_web_is_not_valid(self) -> None:
        cert = _cert(
            masa_berlaku_akhir=PAST,
            p3dn_search_last_seen=PAST,
            p3dn_not_found_since=TODAY,
        )
        assert compute_validity_label(cert, TODAY) == "not_valid"

    def test_past_date_and_unscraped_is_not_valid(self) -> None:
        cert = _cert(masa_berlaku_akhir=PAST)
        assert compute_validity_label(cert, TODAY) == "not_valid"

    def test_no_date_and_present_on_web_is_web_active(self) -> None:
        cert = _cert(p3dn_search_last_seen=TODAY)
        assert compute_validity_label(cert, TODAY) == "web_active"

    def test_no_date_and_lost_from_web_is_not_valid(self) -> None:
        cert = _cert(p3dn_search_last_seen=PAST, p3dn_not_found_since=TODAY)
        assert compute_validity_label(cert, TODAY) == "not_valid"

    def test_no_date_and_unscraped_is_unknown(self) -> None:
        cert = _cert()
        assert compute_validity_label(cert, TODAY) == "unknown"


class TestValidityLabelP3dnTracking:
    def test_seen_on_a_prior_scrape_day_is_still_active(self) -> None:
        """A record found on the last scrape stays 'active' on later days too —
        the day gap alone must not flip it to 'not found'."""
        cert = _cert(p3dn_search_last_seen=date(2026, 6, 20), p3dn_not_found_since=None)
        assert compute_validity_label(cert, TODAY) == "web_active"

    def test_not_found_since_set_overrides_last_seen(self) -> None:
        cert = _cert(
            p3dn_search_last_seen=date(2026, 6, 1),
            p3dn_not_found_since=date(2026, 6, 20),
        )
        assert compute_validity_label(cert, TODAY) == "not_valid"
