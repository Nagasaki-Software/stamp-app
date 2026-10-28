import json

import pytest

from core import identity


@pytest.fixture
def dirs(tmp_path):
    return [tmp_path / "local" / "StampApp", tmp_path / "roaming" / "StampApp"]


@pytest.fixture(autouse=True)
def fixed_user(monkeypatch):
    monkeypatch.setattr(identity, "_current_user", lambda: "alice")


@pytest.fixture(autouse=True)
def hermetic_registry(monkeypatch):
    """実レジストリを汚さないよう試験用サブキーへ退避し、後始末する。"""
    sub = r"Software\StampApp_pytest"
    monkeypatch.setattr(identity, "REG_SUBKEY", sub)
    yield
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
    except Exception:
        pass


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
    # 全保存先（2ファイル＋レジストリ）を改ざんしないと「tampered」にならない
    # （どれか1つでも正規レコードが残れば locked＝改ざん耐性）。
    tampered = json.dumps(
        {"name": "偽 太郎", "win_user": "alice", "created": "x", "sig": "deadbeef"},
        ensure_ascii=False,
    )
    for d in dirs:
        p = d / identity.LOCK_FILENAME
        p.unlink()  # 隠し属性ファイルは直接上書きできないため一旦削除
        p.write_text(tampered, encoding="utf-8")
    identity._reg_write(tampered)  # レジストリも改ざん
    name, status = identity.load_locked_name(dirs)
    assert status == "tampered"
    assert name is None


def test_registry_keeps_lock_when_all_files_deleted(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    for d in dirs:
        (d / identity.LOCK_FILENAME).unlink()  # ファイルを全削除
    name, status = identity.load_locked_name(dirs)
    assert status == "locked"  # レジストリで維持
    assert name == "山田 太郎"


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


ADMIN_KEYWORD = "TEST-KEYWORD"


@pytest.fixture(autouse=True)
def test_admin_key(monkeypatch):
    """本物の管理者キーワードに依存しないよう、テスト用キーワードのハッシュに差し替える。"""
    import hashlib
    monkeypatch.setattr(
        identity, "ADMIN_KEY_HASH", hashlib.sha256(ADMIN_KEYWORD.encode("utf-8")).hexdigest()
    )


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


def test_name_can_be_changed_limited_times(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    assert identity.remaining_name_changes(dirs) == identity.MAX_NAME_CHANGES
    for i in range(identity.MAX_NAME_CHANGES):
        left = identity.change_locked_name(f"山田 {i}", dirs)
        assert left == identity.MAX_NAME_CHANGES - 1 - i
    assert identity.load_locked_name(dirs) == (f"山田 {identity.MAX_NAME_CHANGES - 1}", "locked")
    with pytest.raises(ValueError):
        identity.change_locked_name("もう無理", dirs)


def test_edited_change_count_is_tampered(dirs):
    identity.save_locked_name("山田 太郎", dirs, changes_left=0)
    for d in dirs:
        p = d / identity.LOCK_FILENAME
        rec = json.loads(p.read_text(encoding="utf-8"))
        rec["changes_left"] = 5  # 署名はそのままで回数だけ書き換える
        p.unlink()
        p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    rec = json.loads(identity._reg_read())
    rec["changes_left"] = 5
    identity._reg_write(json.dumps(rec, ensure_ascii=False))
    assert identity.load_locked_name(dirs) == (None, "tampered")
    assert identity.remaining_name_changes(dirs) == 0


def test_restoring_old_copy_does_not_add_changes(dirs):
    identity.save_locked_name("山田 太郎", dirs)
    old = (dirs[0] / identity.LOCK_FILENAME).read_text(encoding="utf-8")
    identity.change_locked_name("鈴木 花子", dirs)
    p = dirs[0] / identity.LOCK_FILENAME
    p.unlink()
    p.write_text(old, encoding="utf-8")  # 変更前の控えを1か所に戻す
    assert identity.load_locked_name(dirs) == ("鈴木 花子", "locked")
    assert identity.remaining_name_changes(dirs) == identity.MAX_NAME_CHANGES - 1


def test_record_without_count_is_still_valid(dirs):
    # 回数制限を入れる前に確定した人の記録は、そのまま使え、上限の回数を変えられる
    rec = {"name": "山田 太郎", "win_user": "alice", "created": "x",
           "sig": identity._sign("山田 太郎", "alice")}
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        (d / identity.LOCK_FILENAME).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    assert identity.load_locked_name(dirs) == ("山田 太郎", "locked")
    assert identity.remaining_name_changes(dirs) == identity.MAX_NAME_CHANGES


def test_admin_override_restores_change_count(dirs):
    identity.save_locked_name("山田 太郎", dirs, changes_left=0)
    _write_override(dirs[0], ADMIN_KEYWORD, "鈴木 花子")
    identity.apply_admin_override(dirs)
    assert identity.remaining_name_changes(dirs) == identity.MAX_NAME_CHANGES
