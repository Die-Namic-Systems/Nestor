"""First browser-key bootstrap creates no signing authority and clobbers nothing."""
from __future__ import annotations

from nestor import cli, keyring


def test_keys_init_creates_an_empty_keyring_and_never_clobbers_it(tmp_path, capsys):
    path = tmp_path / "verifiers.json"

    assert cli.main(["keys", "init", "--keyring", str(path)]) == 0
    assert keyring.load(str(path)).names() == []

    ring = keyring.load(str(path))
    ring.add("sean campbell", key=bytes.fromhex("11" * 32), kind="ed25519")
    ring.save()
    capsys.readouterr()

    assert cli.main(["keys", "init", "--keyring", str(path)]) == 0
    assert keyring.load(str(path)).names() == ["sean campbell"]
    assert "already exists" in capsys.readouterr().out
