"""confine: deterministic profile generation, and the sibling-path denial.

Execution-dependent cases (actually loading a generated profile under
`sandbox-exec`) only make sense on macOS with the binary present; those are
skipped elsewhere with an explicit reason rather than silently passing.
"""

import platform
import shutil

import pytest

import confine
from errors import PreconditionError


def test_seatbelt_profile_generation_is_deterministic(tmp_path):
    writable = tmp_path / "writable"
    writable.mkdir()
    private = tmp_path / "private"
    private.mkdir()

    first = confine.seatbelt_profile(writable_roots=[writable], private_read_root=private)
    second = confine.seatbelt_profile(writable_roots=[writable], private_read_root=private)
    assert first == second


def test_seatbelt_profile_denies_a_sibling_path_inside_the_private_root(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    allowed = private / "allowed-project"
    allowed.mkdir()
    sibling = private / "sibling-project"
    sibling.mkdir()

    profile = confine.seatbelt_profile(
        writable_roots=[allowed],
        private_read_root=private,
        allowed_read_roots=[allowed],
    )

    # The private root is denied wholesale, and only the allowed subpath is
    # reopened; the sibling directory must not appear in any reopened allow.
    assert f'(deny file-read* (subpath "{private.resolve()}"))' in profile
    assert str(sibling.resolve()) not in profile
    assert str(allowed.resolve()) in profile


def test_seatbelt_profile_escapes_special_characters_in_paths(tmp_path):
    tricky = tmp_path / 'weird"name'
    tricky.mkdir()
    private = tmp_path / "private"
    private.mkdir()
    profile = confine.seatbelt_profile(writable_roots=[tricky], private_read_root=private)
    assert '\\"' in profile


def test_available_backend_never_claims_seatbelt_without_the_binary(monkeypatch):
    monkeypatch.setattr(confine.shutil, "which", lambda _name: None)
    assert confine.available_backend() == "deny"


def test_confine_refuses_without_a_private_read_root():
    with pytest.raises(confine.IsolationRefused):
        confine.confine(writable_roots=[], private_read_root=None)


def test_confine_refuses_none_backend_for_writing_work(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(confine.IsolationRefused):
        confine.confine(writable_roots=[], private_read_root=private, read_only=False, backend="none")


def test_confine_none_backend_accepted_for_read_only_work(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    result = confine.confine(writable_roots=[], private_read_root=private, read_only=True, backend="none")
    assert result.backend == "none"


def test_confine_refuses_runtime_native_without_observation(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(confine.IsolationRefused):
        confine.confine(
            writable_roots=[private], private_read_root=private,
            runtime_confines_itself=False, backend="runtime_native",
        )


def test_confine_deny_backend_always_refuses(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(confine.IsolationRefused):
        confine.confine(writable_roots=[private], private_read_root=private, backend="deny")


def test_confine_unknown_backend_is_a_precondition_error(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(PreconditionError):
        confine.confine(writable_roots=[private], private_read_root=private, backend="not-a-real-backend")


@pytest.mark.skipif(
    platform.system() != "Darwin" or shutil.which("sandbox-exec") is None,
    reason="seatbelt execution requires macOS with sandbox-exec present; skipped rather than silently passed",
)
def test_seatbelt_profile_actually_loads_under_sandbox_exec(tmp_path):
    import subprocess

    writable = tmp_path / "writable"
    writable.mkdir()
    private = tmp_path / "private"
    private.mkdir()
    profile = confine.seatbelt_profile(writable_roots=[writable], private_read_root=private)
    profile_path = tmp_path / "profile.sb"
    profile_path.write_text(profile)
    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-f", str(profile_path), "/bin/echo", "confined"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "confined" in result.stdout
