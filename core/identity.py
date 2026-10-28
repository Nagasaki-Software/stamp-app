"""印鑑名のロック（偽造防止）。署名付きロックファイルの読み書きと管理者override。

手軽重視モデル：普通の利用者の名前付け替えを実質不可能にする。SIGNING_SECRET は
ビルド時に EXE へ埋め込み（高度な攻撃は対象外）。
"""
import getpass
import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# 秘密値は Git 管理外の core/_secrets.py から読む（平文の管理者キーワードは保存しない）。
# 無い場合は開発用の値で動く。開発用の値は公開されているため、配布ビルドには使わない。
try:
    from core._secrets import ADMIN_KEY_HASH, SIGNING_SECRET
except ImportError:
    SIGNING_SECRET = "dev-only-signing-secret"
    ADMIN_KEY_HASH = hashlib.sha256(b"dev-admin-keyword").hexdigest()

LOCK_FILENAME = "identity.lock"
OVERRIDE_FILENAME = "admin_override.txt"


def _current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _lock_dirs() -> list[Path]:
    """ロックファイルの保存ディレクトリ（主=LOCALAPPDATA, 副=APPDATA）。"""
    dirs: list[Path] = []
    for env in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / "StampApp")
    if not dirs:
        dirs.append(Path.home() / ".stampapp")
    return dirs


def _sign(name: str, win_user: str) -> str:
    msg = (name + "|" + win_user).encode("utf-8")
    return hmac.new(SIGNING_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _set_hidden(path: Path) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)  # HIDDEN
    except Exception:
        pass


# レジストリ保存先（HKEY_CURRENT_USER＝自分の領域、管理者権限不要）
REG_SUBKEY = r"Software\StampApp"
REG_VALUE_NAME = "identity"


def _reg_write(data: str) -> None:
    """署名付きレコードを HKCU レジストリへ書き込む（失敗しても致命的でない）。"""
    try:
        import winreg
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, data)
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass


def _reg_read() -> Optional[str]:
    """HKCU レジストリから署名付きレコードを読む。無ければ None。"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_QUERY_VALUE
        )
        try:
            val, _ = winreg.QueryValueEx(key, REG_VALUE_NAME)
            return val if isinstance(val, str) else None
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def save_locked_name(name: str, dirs: Optional[list[Path]] = None) -> None:
    """署名付きロックレコードを全ディレクトリへ書き込む。"""
    dirs = dirs or _lock_dirs()
    win_user = _current_user()
    rec = {
        "name": name,
        "win_user": win_user,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sig": _sign(name, win_user),
    }
    data = json.dumps(rec, ensure_ascii=False)
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / LOCK_FILENAME
            if p.exists():
                p.unlink()  # 隠し属性ファイルへの上書き失敗を回避（再署名/override対応）
            p.write_text(data, encoding="utf-8")
            _set_hidden(p)
        except Exception:
            continue
    _reg_write(data)  # レジストリにも保存（ファイル全削除でもロックを維持）


def load_locked_name(dirs: Optional[list[Path]] = None) -> tuple[Optional[str], str]:
    """戻り値 (name|None, status)。status は 'locked'/'unlocked'/'tampered'。"""
    dirs = dirs or _lock_dirs()
    win_user = _current_user()

    # 候補レコード（生JSON文字列）をファイル群＋レジストリから集める
    raws: list[str] = []
    for d in dirs:
        p = d / LOCK_FILENAME
        if p.exists():
            try:
                raws.append(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    reg = _reg_read()
    if reg:
        raws.append(reg)

    found_for_user = False
    for raw in raws:
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if rec.get("win_user") != win_user:
            continue  # 他アカウントのロックは自分に無関係
        found_for_user = True
        expected = _sign(rec.get("name", ""), win_user)
        if hmac.compare_digest(expected, str(rec.get("sig", ""))):
            return rec.get("name"), "locked"
    if found_for_user:
        return None, "tampered"
    return None, "unlocked"


def apply_admin_override(dirs: Optional[list[Path]] = None) -> tuple[str, Optional[str]]:
    """管理者override ファイルを処理。戻り値 (status, name)。

    status: 'applied'（適用・消費）/ 'bad_keyword'（不正）/ 'none'（ファイル無し）。
    """
    dirs = dirs or _lock_dirs()
    override_path = None
    for d in dirs:
        p = d / OVERRIDE_FILENAME
        if p.exists():
            override_path = p
            break
    if override_path is None:
        return "none", None

    try:
        text = override_path.read_text(encoding="utf-8")
    except Exception:
        return "none", None

    kv: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()
    keyword = kv.get("keyword", "")
    new_name = kv.get("name", "")

    if hashlib.sha256(keyword.encode("utf-8")).hexdigest() != ADMIN_KEY_HASH or not new_name:
        return "bad_keyword", None

    save_locked_name(new_name, dirs)
    for d in dirs:  # 全ディレクトリの override を消費
        try:
            (d / OVERRIDE_FILENAME).unlink()
        except Exception:
            pass
    return "applied", new_name
