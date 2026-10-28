"""CSV形式の押印履歴ログ（UTF-8 BOM付き、追記モード、ハッシュチェーン付き、デバイス名記録）。

各行は SHA256(前行ハッシュ + 当行データ) を保持し、改ざんを検知できる。
hostname 列でアプリを使用したPCを特定できる。
verify_log() で全行を検証できる。
"""
import csv
import hashlib
from pathlib import Path

from core.edition import DATA_NAME

LOG_HEADERS = [
    "timestamp",
    "pdf_path",
    "pages",
    "stamp_name",
    "stamp_date",
    "stamp_affiliation",
    "hostname",
    "prev_hash",
    "row_hash",
]

DATA_COL_COUNT = 7  # ハッシュを除いた実データ列数（hostname含む）
GENESIS_HASH = "GENESIS"


def default_log_path() -> Path:
    return Path.home() / "Documents" / DATA_NAME / "stamp_log.csv"


def _hash_row(prev_hash: str, data_cols: list[str]) -> str:
    payload = prev_hash + "|" + "|".join(data_cols)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_last_hash(log_path: Path) -> str:
    if not log_path.exists():
        return GENESIS_HASH
    last = GENESIS_HASH
    with log_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row == LOG_HEADERS:
                continue
            if len(row) >= len(LOG_HEADERS):
                last = row[-1] or last
    return last


def _is_current_format(log_path: Path) -> bool:
    if not log_path.exists():
        return True
    try:
        with log_path.open(encoding="utf-8-sig", newline="") as f:
            first = next(csv.reader(f), None)
    except Exception:
        return False
    return first == LOG_HEADERS


def _archive_legacy(log_path: Path) -> Path:
    from datetime import datetime
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived = log_path.with_name(f"{log_path.stem}.legacy.{suffix}.csv")
    log_path.rename(archived)
    return archived


def _data_cols(timestamp, pdf_path, pages, stamp_name, stamp_date, stamp_affiliation, hostname) -> list[str]:
    return [
        timestamp,
        pdf_path,
        ",".join(str(p) for p in pages),
        stamp_name,
        stamp_date,
        stamp_affiliation,
        hostname,
    ]


def next_row_hash(
    log_path: Path,
    timestamp: str,
    pdf_path: str,
    pages: list[int],
    stamp_name: str,
    stamp_date: str,
    stamp_affiliation: str,
    hostname: str,
) -> str:
    """append_log に同じ値を渡したときに返る row_hash を、ログに書かずに求める。

    押印に成功してからログに書くため、PDFメタデータ用のハッシュを先に知る必要がある。
    """
    fresh = not log_path.exists() or not _is_current_format(log_path)
    prev_hash = GENESIS_HASH if fresh else _read_last_hash(log_path)
    return _hash_row(
        prev_hash,
        _data_cols(timestamp, pdf_path, pages, stamp_name, stamp_date, stamp_affiliation, hostname),
    )


def append_log(
    log_path: Path,
    timestamp: str,
    pdf_path: str,
    pages: list[int],
    stamp_name: str,
    stamp_date: str,
    stamp_affiliation: str,
    hostname: str,
) -> str:
    """1行追記し、当該行の row_hash を返す（PDFメタデータ等に埋め込めるよう）。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists() and not _is_current_format(log_path):
        _archive_legacy(log_path)
    is_new = not log_path.exists()
    prev_hash = GENESIS_HASH if is_new else _read_last_hash(log_path)

    data_cols = _data_cols(
        timestamp, pdf_path, pages, stamp_name, stamp_date, stamp_affiliation, hostname
    )
    row_hash = _hash_row(prev_hash, data_cols)

    with log_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(LOG_HEADERS)
        writer.writerow(data_cols + [prev_hash, row_hash])
    return row_hash


def verify_log(
    log_path: Path,
) -> tuple[bool, list[int], list[int]]:
    """ログ全体のハッシュチェーンを検証。

    返り値: (is_valid, tampered_row_numbers, legacy_row_numbers)
    """
    if not log_path.exists():
        return True, [], []

    with log_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return True, [], []

    header = rows[0]
    if header != LOG_HEADERS:
        return False, [], list(range(1, len(rows)))

    tampered: list[int] = []
    legacy: list[int] = []
    prev_hash = GENESIS_HASH

    for i, row in enumerate(rows[1:], start=1):
        if len(row) < len(LOG_HEADERS):
            legacy.append(i)
            return False, tampered, legacy + list(range(i + 1, len(rows)))

        data_cols = row[:DATA_COL_COUNT]
        stored_prev = row[DATA_COL_COUNT]
        stored_hash = row[DATA_COL_COUNT + 1]

        if stored_prev != prev_hash:
            tampered.append(i)
        expected = _hash_row(stored_prev, data_cols)
        if expected != stored_hash:
            if i not in tampered:
                tampered.append(i)
        prev_hash = stored_hash

    is_valid = not tampered and not legacy
    return is_valid, tampered, legacy
