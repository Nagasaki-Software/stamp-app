import csv

from core.logger import LOG_HEADERS, append_log, verify_log


def _read_rows(log_path):
    with log_path.open(encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def _append(log_path, **overrides):
    base = dict(
        timestamp="2026-05-23 14:32:18",
        pdf_path="a.pdf",
        pages=[1],
        stamp_name="n",
        stamp_date="d",
        stamp_affiliation="a",
        hostname="DESKTOP-ABC123",
    )
    base.update(overrides)
    return append_log(log_path, **base)


def test_creates_file_with_headers_on_first_call(tmp_path):
    log_path = tmp_path / "stamp_log.csv"
    h = _append(
        log_path,
        timestamp="2026-05-23 14:32:18",
        pdf_path=r"C:\foo\契約書.pdf",
        pages=[2, 3, 5],
        stamp_name="山田 太郎",
        stamp_date="'26.05.23",
        stamp_affiliation="営業部",
        hostname="TEST-PC",
    )
    rows = _read_rows(log_path)
    assert rows[0] == LOG_HEADERS
    assert rows[1][:7] == [
        "2026-05-23 14:32:18",
        r"C:\foo\契約書.pdf",
        "2,3,5",
        "山田 太郎",
        "'26.05.23",
        "営業部",
        "TEST-PC",
    ]
    assert rows[1][7] == "GENESIS"
    assert rows[1][8] == h
    assert len(h) == 64


def test_appends_with_hash_chain(tmp_path):
    log_path = tmp_path / "stamp_log.csv"
    hashes = [_append(log_path, timestamp=f"2026-05-23 14:32:{i:02d}") for i in range(3)]
    rows = _read_rows(log_path)
    assert len(rows) == 4
    assert rows[1][7] == "GENESIS"
    assert rows[2][7] == hashes[0]
    assert rows[3][7] == hashes[1]


def test_hostname_is_included_in_hash(tmp_path):
    """同じ内容でも hostname が違えばハッシュは別になること。"""
    log1 = tmp_path / "log1.csv"
    log2 = tmp_path / "log2.csv"
    h1 = _append(log1, hostname="PC-A")
    h2 = _append(log2, hostname="PC-B")
    assert h1 != h2


def test_verify_passes_for_untampered_log(tmp_path):
    log_path = tmp_path / "stamp_log.csv"
    for i in range(3):
        _append(log_path, timestamp=f"2026-05-23 14:32:{i:02d}")
    is_valid, tampered, legacy = verify_log(log_path)
    assert is_valid is True
    assert tampered == []
    assert legacy == []


def test_verify_detects_hostname_tampering(tmp_path):
    """hostname の書き換えも検知すること。"""
    log_path = tmp_path / "stamp_log.csv"
    for i in range(3):
        _append(log_path, timestamp=f"2026-05-23 14:32:{i:02d}")
    rows = _read_rows(log_path)
    rows[2][6] = "OTHER-PC"
    with log_path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    is_valid, tampered, _ = verify_log(log_path)
    assert is_valid is False
    assert 2 in tampered


def test_verify_detects_row_deletion(tmp_path):
    log_path = tmp_path / "stamp_log.csv"
    for i in range(3):
        _append(log_path, timestamp=f"2026-05-23 14:32:{i:02d}")
    rows = _read_rows(log_path)
    del rows[2]
    with log_path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    is_valid, tampered, _ = verify_log(log_path)
    assert is_valid is False
    assert tampered != []
