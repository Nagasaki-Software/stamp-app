# 名前ロック（偽造防止）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 印鑑の名前を一度確定したらグレーアウトして変更不可にし、管理者だけがファイル方式（キーワード）で変更でき、`settings.json` を消しても署名付き別ファイルでロックが残るようにする。

**Architecture:** 名前のロックは `core/identity.py` に集約。`%LOCALAPPDATA%` と `%APPDATA%` の2か所に署名付き(HMAC-SHA256)レコード `identity.lock` を保存し、Windowsアカウントに紐付ける。GUIは起動時に管理者override→ロック読込を行い、ロック時は名前欄をdisabled。初回押印時に確認ダイアログで確定。レジストリ・外部ライブラリは不使用（標準ライブラリのみ）。

**Tech Stack:** Python 3.13 / hashlib・hmac・json・getpass・ctypes（隠し属性）/ customtkinter / pytest / PyInstaller

> **本プロジェクト規約（重要）**
> - **コミットはユーザーの明示指示時のみ実行**。各タスクの「Commit」手順は指示があるまで実行せず次へ進んでよい。
> - 作業ディレクトリ（cwd）は `stamp_app/`。Pythonは `.venv\Scripts\python.exe`。
> - `dist/StampApp/使い方.txt`・`StampApp.zip` の上書きは事前確認の上で行う。
> - **管理者キーワード平文（`（非公開）`）は配布物・使い方.txtに書かない**（管理者にのみ共有）。

---

## ファイル構成（このプランで触る範囲）

**新規作成**
- `core/identity.py` — 内蔵定数・署名/検証・ロック読み書き(主/副)・管理者override処理
- `tests/test_identity.py` — 署名/検証・改ざん検知・win_user不一致・冗長保存・override のテスト

**部分改修**
- `gui/stamp_panel.py` — 名前欄を `self.name_entry` に保持、`name_locked` でdisabled、`lock_name()` 追加、`values()` は従来通り
- `gui/app.py` — 起動時に override 適用→ロック読込、ロック反映、改ざん時は押印停止、初回押印時に確定ダイアログ

**変更しない**
- `core/settings.py`（名前の優先はapp側で処理）、`core/logger.py`、`core/pdf_stamper.py`、`core/stamp_generator.py`、`core/markers.py`、`core/mark_detector.py`

**パッケージング**
- `dist/StampApp/使い方.txt` 更新、EXE再ビルド、`StampApp.zip` 再作成

---

## Task 1: core/identity.py — 署名・保存・読込

**Files:**
- Create: `core/identity.py`
- Test: `tests/test_identity.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_identity.py` を新規作成：

```python
import json

import pytest

from core import identity


@pytest.fixture
def dirs(tmp_path):
    return [tmp_path / "local" / "StampApp", tmp_path / "roaming" / "StampApp"]


@pytest.fixture(autouse=True)
def fixed_user(monkeypatch):
    monkeypatch.setattr(identity, "_current_user", lambda: "alice")


def test_sign_is_deterministic_and_bound_to_user():
    a = identity._sign("山田 太郎", "alice")
    b = identity._sign("山田 太郎", "alice")
    c = identity._sign("山田 太郎", "bob")
    assert a == b
    assert a != c  # アカウントに紐付く


def test_save_then_load_is_locked(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    name, status = identity.load_locked_name(dirs)
    assert status == "locked"
    assert name == "山田 太郎"


def test_no_files_is_unlocked(dirs):
    name, status = identity.load_locked_name(dirs)
    assert status == "unlocked"
    assert name is None


def test_tampered_name_is_detected(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    # 署名を変えずに name を書き換える（手書き改ざん）
    p = dirs[0] / identity.LOCK_FILENAME
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["name"] = "偽 太郎"
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    # 副も同様に改ざん
    p2 = dirs[1] / identity.LOCK_FILENAME
    rec2 = json.loads(p2.read_text(encoding="utf-8"))
    rec2["name"] = "偽 太郎"
    p2.write_text(json.dumps(rec2, ensure_ascii=False), encoding="utf-8")
    name, status = identity.load_locked_name(dirs)
    assert status == "tampered"
    assert name is None


def test_other_user_record_is_ignored(dirs, monkeypatch):
    identity.save_locked_name("山田 太郎", dirs)  # alice として保存
    monkeypatch.setattr(identity, "_current_user", lambda: "bob")
    name, status = identity.load_locked_name(dirs)
    assert status == "unlocked"  # bob には無関係


def test_redundancy_secondary_survives_primary_delete(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    (dirs[0] / identity.LOCK_FILENAME).unlink()  # 主を削除
    name, status = identity.load_locked_name(dirs)
    assert status == "locked"  # 副で維持
    assert name == "山田 太郎"
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_identity.py -v`
Expected: FAIL（`ModuleNotFoundError: core.identity`）

- [ ] **Step 3: 実装**

`core/identity.py` を新規作成：

```python
"""印鑑名のロック（偽造防止）。署名付きロックファイルの読み書きと管理者override。

手軽重視モデル：普通の利用者の名前付け替えを実質不可能にする。SIGNING_SECRET は
平文埋め込み（高度な攻撃は対象外）。レジストリ不使用・ファイルのみ。
"""
import getpass
import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# アプリ内蔵の定数（ビルド時に固定。平文の管理者キーワードは保存しない）
SIGNING_SECRET = "（非公開：core/_secrets.py）"
ADMIN_KEY_HASH = "（非公開：core/_secrets.py）"

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
            p.write_text(data, encoding="utf-8")
            _set_hidden(p)
        except Exception:
            continue


def load_locked_name(dirs: Optional[list[Path]] = None) -> tuple[Optional[str], str]:
    """戻り値 (name|None, status)。status は 'locked'/'unlocked'/'tampered'。"""
    dirs = dirs or _lock_dirs()
    win_user = _current_user()
    found_for_user = False
    for d in dirs:
        p = d / LOCK_FILENAME
        if not p.exists():
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_identity.py -v`
Expected: PASS（6件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/identity.py tests/test_identity.py
git commit -m "feat: add signed name-lock storage (identity.py)"
```

---

## Task 2: core/identity.py — 管理者override

**Files:**
- Modify: `core/identity.py`
- Test: `tests/test_identity.py`

> 管理者キーワード平文 `（非公開）` は `ADMIN_KEY_HASH` に対応する（SHA256）。テストでのみ平文を使う。

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_identity.py` の末尾に追記：

```python
ADMIN_KEYWORD = "（非公開）"  # ADMIN_KEY_HASH に対応（テスト用）


def _write_override(dir_path, keyword, name):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / identity.OVERRIDE_FILENAME).write_text(
        f"keyword={keyword}\nname={name}\n", encoding="utf-8"
    )


def test_override_with_valid_keyword_updates_and_consumes(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    _write_override(dirs[0], ADMIN_KEYWORD, "鈴木 花子")
    status, new_name = identity.apply_admin_override(dirs)
    assert status == "applied"
    assert new_name == "鈴木 花子"
    # override ファイルは消費される
    assert not (dirs[0] / identity.OVERRIDE_FILENAME).exists()
    # ロックが新しい名前で再署名されている
    name, lock_status = identity.load_locked_name(dirs)
    assert lock_status == "locked"
    assert name == "鈴木 花子"


def test_override_with_bad_keyword_does_nothing(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    _write_override(dirs[0], "WRONG-KEYWORD", "鈴木 花子")
    status, new_name = identity.apply_admin_override(dirs)
    assert status == "bad_keyword"
    name, lock_status = identity.load_locked_name(dirs)
    assert name == "山田 太郎"  # 変わらない


def test_override_absent_is_none(dirs):
    status, new_name = identity.apply_admin_override(dirs)
    assert status == "none"
    assert new_name is None
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_identity.py::test_override_with_valid_keyword_updates_and_consumes -v`
Expected: FAIL（`AttributeError: apply_admin_override`）

- [ ] **Step 3: 実装**

`core/identity.py` の末尾に追記：

```python
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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_identity.py -v`
Expected: PASS（9件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/identity.py tests/test_identity.py
git commit -m "feat: add admin override for name lock"
```

---

## Task 3: gui/stamp_panel.py — 名前欄のロック対応

**Files:**
- Modify: `gui/stamp_panel.py`（`__init__` 引数・名前欄・`lock_name()` 追加）

- [ ] **Step 1: `__init__` 引数に name_locked を追加**

変更前：
```python
    def __init__(
        self,
        master,
        fonts: dict[str, Path],
        initial: dict,
        on_change=None,
    ):
        super().__init__(master)
        self._on_change = on_change or (lambda: None)
        self._fonts = fonts
```
変更後：
```python
    def __init__(
        self,
        master,
        fonts: dict[str, Path],
        initial: dict,
        on_change=None,
        name_locked: bool = False,
    ):
        super().__init__(master)
        self._on_change = on_change or (lambda: None)
        self._fonts = fonts
```

- [ ] **Step 2: 名前欄を参照保持し、ロック時はdisabled**

変更前：
```python
        # 名前
        ctk.CTkLabel(self, text="名前").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.name_var = ctk.StringVar(value=initial.get("name", ""))
        ctk.CTkEntry(self, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )
```
変更後：
```python
        # 名前（ロック時は編集不可＝グレーアウト）
        ctk.CTkLabel(self, text="名前").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.name_var = ctk.StringVar(value=initial.get("name", ""))
        self.name_entry = ctk.CTkEntry(self, textvariable=self.name_var)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        if name_locked:
            self.name_entry.configure(state="disabled")
```

- [ ] **Step 3: lock_name() メソッドを追加**

`def selected_font_path(self) -> Path:` の直前に追加：

```python
    def lock_name(self):
        """名前欄を編集不可（グレーアウト）にする。初回確定時に呼ぶ。"""
        self.name_entry.configure(state="disabled")

```

- [ ] **Step 4: import確認**

Run: `.venv\Scripts\python.exe -c "import gui.stamp_panel as s; print('OK', s.StampPanel)"`
Expected: `OK <class 'gui.stamp_panel.StampPanel'>`

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add gui/stamp_panel.py
git commit -m "feat: support locked (disabled) name field in stamp panel"
```

---

## Task 4: gui/app.py — 起動時ロック適用・初回確定・改ざん停止

**Files:**
- Modify: `gui/app.py`（import・__init__・StampPanel生成・状態・_on_execute・起動通知）

- [ ] **Step 1: import を追加**

変更前：
```python
from core.mark_detector import detect_marks
from core.markers import export_all
```
変更後：
```python
from core.identity import apply_admin_override, load_locked_name, save_locked_name
from core.mark_detector import detect_marks
from core.markers import export_all
```

- [ ] **Step 2: 起動時に override 適用→ロック読込**

変更前：
```python
        self._fonts = list_fonts(FONTS_DIR)
        self._settings = load_settings()
        # PCのデバイス名（ホスト名）をログとPDFメタデータに記録する
        try:
            self._hostname = socket.gethostname()
        except Exception:
            self._hostname = "unknown"
```
変更後：
```python
        self._fonts = list_fonts(FONTS_DIR)
        self._settings = load_settings()
        # PCのデバイス名（ホスト名）をログとPDFメタデータに記録する
        try:
            self._hostname = socket.gethostname()
        except Exception:
            self._hostname = "unknown"

        # 名前ロック（偽造防止）：管理者override→ロック読込
        self._startup_notices: list[tuple[str, str]] = []
        self._name_locked = False
        self._identity_tampered = False
        ov_status, ov_name = apply_admin_override()
        if ov_status == "applied":
            self._startup_notices.append(("info", f"管理者により名前を変更しました：{ov_name}"))
        elif ov_status == "bad_keyword":
            self._startup_notices.append(("error", "管理者キーワードが正しくありません。"))
        locked_name, lock_status = load_locked_name()
        if lock_status == "locked":
            self._name_locked = True
            self._settings["name"] = locked_name
        elif lock_status == "tampered":
            self._name_locked = True
            self._identity_tampered = True
            self._settings["name"] = ""
            self._startup_notices.append(
                ("error", "本人名情報が破損/改ざんされています。管理者に連絡してください。")
            )
```

- [ ] **Step 3: StampPanel にロック状態を渡す**

変更前：
```python
        self.stamp_panel = StampPanel(
            self.left,
            fonts=self._fonts,
            initial=self._settings,
            on_change=self._on_settings_change,
        )
```
変更後：
```python
        self.stamp_panel = StampPanel(
            self.left,
            fonts=self._fonts,
            initial=self._settings,
            on_change=self._on_settings_change,
            name_locked=self._name_locked,
        )
```

- [ ] **Step 4: __init__ 末尾で起動通知を表示予約**

変更前：
```python
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_settings_change()
```
変更後：
```python
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_settings_change()
        if self._startup_notices:
            self.after(300, self._flush_startup_notices)

    def _flush_startup_notices(self):
        for kind, msg in self._startup_notices:
            if kind == "error":
                messagebox.showerror("StampApp", msg)
            else:
                messagebox.showinfo("StampApp", msg)
        self._startup_notices = []
```

- [ ] **Step 5: _on_execute に改ざん停止と初回確定を挿入**

変更前：
```python
        target_count = sum(1 for rs in self._detections.values() if rs)
        if target_count == 0:
            messagebox.showinfo("StampApp", "選択中のマークが検出されませんでした")
            return
        if not messagebox.askokcancel(
            "StampApp",
            f"PDFを上書きします。よろしいですか？\n対象: {target_count} ページ",
        ):
            return
```
変更後：
```python
        target_count = sum(1 for rs in self._detections.values() if rs)
        if target_count == 0:
            messagebox.showinfo("StampApp", "選択中のマークが検出されませんでした")
            return
        # 名前情報が改ざんされている場合は押印を止める（偽名押印を許さない）
        if self._identity_tampered:
            messagebox.showerror(
                "StampApp", "本人名情報が破損/改ざんされています。管理者に連絡してください。"
            )
            return
        # 未ロックなら初回押印時に名前を確定（以後は管理者キーワードでのみ変更）
        if not self._name_locked:
            name_now = self.stamp_panel.values()["name"].strip()
            if not name_now:
                messagebox.showwarning("StampApp", "名前が入力されていません")
                return
            if not messagebox.askokcancel(
                "StampApp 名前の確定",
                f"この名前『{name_now}』で確定します。\n"
                "以後の変更には管理者キーワードが必要です。よろしいですか？",
            ):
                return
            save_locked_name(name_now)
            self._name_locked = True
            self.stamp_panel.lock_name()
        if not messagebox.askokcancel(
            "StampApp",
            f"PDFを上書きします。よろしいですか？\n対象: {target_count} ページ",
        ):
            return
```

- [ ] **Step 6: import確認とテスト**

Run: `.venv\Scripts\python.exe -c "import gui.app; print('OK')"`
Expected: `OK`

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: 既存＋新規（identity 9件）すべてPASS。

- [ ] **Step 7: 起動スモークテスト（手動）**

Run: `.venv\Scripts\python.exe main.py`
Expected: ウィンドウが開く。初回は名前欄が編集可能。名前を入れて「押印実行」→確定ダイアログ→OKで以後グレーアウト。エラーダイアログが出ない。確認後ウィンドウを閉じる。

- [ ] **Step 8: Commit（指示時のみ）**

```bash
git add gui/app.py
git commit -m "feat: enforce name lock at startup and on first stamp"
```

---

## Task 5: EXE再ビルド・使い方.txt更新・配布ZIP

**Files:**
- 生成: `dist/StampApp/`、作成/更新: `dist/StampApp/使い方.txt`、作成: `StampApp.zip`

- [ ] **Step 1: 起動中のEXEを終了（あれば）**

Run: `taskkill //F //IM StampApp.exe`
Expected: 終了する。起動していなければ「見つかりません」で問題なし。

- [ ] **Step 2: EXEをビルド**

Run: `.venv\Scripts\python.exe -m PyInstaller build.spec --clean --noconfirm`
Expected: `dist\StampApp\StampApp.exe` が生成（`core/identity.py` は自動的に取り込まれる）。

- [ ] **Step 3: 使い方.txt を更新（上書き確認の上）**

> 管理者キーワード平文は記載しない。`dist/StampApp/使い方.txt` の「ログ」項目の前に、次の節を追記する（既存の他項目は維持）。

追記する内容：
```
■ 名前のロック（偽造防止）
・名前を入れて初めて「押印実行」すると、確認のうえ名前が確定します。
　以後、名前欄はグレーアウトして変更できません（所属・色・サイズ等は変更可）。
・設定ファイル(settings.json)を消しても、名前のロックは別の場所に残ります。

■ 管理者による名前変更（管理者のみ）
1) 次のフォルダにテキストファイル「admin_override.txt」を作成
   %LOCALAPPDATA%\StampApp\admin_override.txt
2) 中身を次の2行にする（キーワードは管理者から配布されたもの）
   keyword=（管理者キーワード）
   name=新しい名前
3) アプリを起動すると、名前が更新され、このファイルは自動で消えます
   （キーワードが違うと変更されません）
```

- [ ] **Step 4: EXEで動作確認（手動）**

`dist\StampApp\StampApp.exe` を起動 → 名前を確定 → 再起動して名前欄がグレーアウトしているか確認 → `admin_override.txt`（正しいキーワード）で名前変更できるか確認。
Expected: 確定後はグレーアウト、override で変更可、誤キーワードでは変更されない。

- [ ] **Step 5: 配布ZIPを作成（上書き確認の上）**

Run:
```bash
.venv\Scripts\python.exe -c "import shutil; shutil.make_archive('StampApp','zip',root_dir='dist',base_dir='StampApp'); print('done')"
```
Expected: `StampApp.zip` が再作成される。

- [ ] **Step 6: 完了報告**

ユーザーへ：管理者キーワード `（非公開）` を管理者にのみ共有するよう伝える。実機で「確定→グレーアウト」「settings.json削除後もロック維持」「管理者override」を確認してもらう。

---

## 自己レビュー結果（記入済み）

- **仕様カバレッジ**：spec §3 ロック保存=Task1（主/副・署名・win_user）、§4 検証/改ざん=Task1（tampered）＋Task4（押印停止）、§5 タイミング/UX=Task3（disabled）＋Task4（初回確定ダイアログ）、§6 管理者override=Task2＋Task4（起動時適用）、§7 内蔵定数=Task1、§8 既存関係=settings/logger等は無改修（app側で名前優先）、§9 ファイル=全タスクに対応、§10 テスト=Task1/2、使い方=Task5。→ 欠落なし。
- **settings.py**：spec §9 では改修対象だが、名前の優先は app 起動時に `self._settings["name"]` を上書きして処理するため `settings.py` 自体は無改修（最小変更）。
- **プレースホルダ**：TBD/TODO無し。各コードステップに実体コードあり。`admin_override.txt` 内の「（管理者キーワード）」は管理者が記入する箇所であり実装上のプレースホルダではない。
- **型・名称整合**：`save_locked_name(name, dirs=None)` / `load_locked_name(dirs=None)->(name,status)` / `apply_admin_override(dirs=None)->(status,name)` / `StampPanel(..., name_locked=False)` / `lock_name()` は全タスクで一致。status 値 'locked'/'unlocked'/'tampered'・'applied'/'bad_keyword'/'none' は Task1/2/4 で一致。
```
