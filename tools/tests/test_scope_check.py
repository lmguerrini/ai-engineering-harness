"""The full attack matrix scope_check has to refuse.

This is the highest-value test file in the toolbelt: `normalise` and `within`
resisted every attack across four kernel audit rounds, and this file is the
regression lock for each one.
"""

import subprocess
import sys
from pathlib import Path

import scope_check

TOOLS_DIR = Path(__file__).resolve().parent.parent


def test_ordinary_relative_path_normalises():
    assert scope_check.normalise("src/loader.py") == "src/loader.py"


def test_dot_segments_collapse():
    assert scope_check.normalise("./src/loader.py") == "src/loader.py"
    assert scope_check.normalise("src/./loader.py") == "src/loader.py"


def test_trailing_slash_is_stripped():
    assert scope_check.normalise("src/loader/") == "src/loader"


def test_parent_climbing_is_refused():
    assert scope_check.normalise("../etc/passwd") is None
    assert scope_check.normalise("src/../../etc/passwd") is None
    assert scope_check.normalise("..") is None


def test_climbing_that_stays_inside_still_refused_or_normalises_safely():
    # `src/x/../y` normalises to `src/y`, which is a legitimate collapse, not
    # an escape — the escape rule is about leaving the root, not about `..`
    # appearing anywhere in the input.
    assert scope_check.normalise("src/x/../y") == "src/y"


def test_absolute_posix_path_is_refused():
    assert scope_check.normalise("/etc/passwd") is None


def test_absolute_windows_backslash_path_is_refused():
    assert scope_check.normalise("\\etc\\passwd") is None


def test_unc_path_is_refused():
    assert scope_check.normalise("\\\\server\\share\\secret") is None


def test_drive_letter_is_refused():
    assert scope_check.normalise("C:\\Users\\secret") is None
    assert scope_check.normalise("C:/Users/secret") is None


def test_nul_byte_is_not_refused_by_shape_but_stays_a_string():
    # A NUL byte does not itself defeat normalisation (posixpath does not
    # treat it specially), but it must never crash the boundary check, and the
    # normalised value must not silently drop the byte in a way that changes
    # containment.
    normal = scope_check.normalise("src/lo\x00ader.py")
    assert normal is not None
    assert "\x00" in normal


def test_leading_whitespace_is_refused():
    assert scope_check.normalise(" src/loader.py") is None


def test_trailing_whitespace_is_refused():
    assert scope_check.normalise("src/loader.py ") is None


def test_internal_whitespace_is_preserved_not_refused():
    assert scope_check.normalise("src/lo ader.py") == "src/lo ader.py"


def test_non_string_input_is_refused():
    assert scope_check.normalise(None) is None
    assert scope_check.normalise(123) is None
    assert scope_check.normalise(["src/loader.py"]) is None


def test_empty_string_is_refused():
    assert scope_check.normalise("") is None


def test_symlink_shaped_name_normalises_like_any_other_path():
    # A path that merely *looks* like it names a symlink is not special: the
    # boundary rule operates on the string, and resolving symlinks is a
    # filesystem question this module does not answer.
    assert scope_check.normalise("src/link-to-secret") == "src/link-to-secret"


def test_within_matches_root_itself():
    assert scope_check.within("src", "src") is True


def test_within_matches_child():
    assert scope_check.within("src/loader.py", "src") is True


def test_within_rejects_sibling_with_shared_prefix():
    # `src2` starts with `src` as a raw string but is not inside it; the
    # missing `/` boundary is exactly the bug this guards against.
    assert scope_check.within("src2/loader.py", "src") is False


def test_within_is_case_sensitive():
    assert scope_check.within("SRC/loader.py", "src") is False


def test_normalise_all_partitions_good_and_bad():
    good, bad = scope_check.normalise_all(["src/a.py", "/etc/passwd", "../x", "b.py"])
    assert good == ("src/a.py", "b.py")
    assert bad == ("/etc/passwd", "../x")


def test_normalise_all_refuses_non_list_wholesale():
    good, bad = scope_check.normalise_all("src/a.py")
    assert good == ()
    assert bad == ("src/a.py",)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "scope_check.py"), *args],
        capture_output=True, text=True, cwd=str(TOOLS_DIR),
    )


def test_cli_reports_contained_and_exits_zero():
    result = _run_cli("--allow", "src", "src/loader.py")
    assert result.returncode == 0
    assert "CONTAINED" in result.stdout


def test_cli_reports_refusal_and_exits_nonzero():
    result = _run_cli("--allow", "src", "/etc/passwd")
    assert result.returncode != 0
    assert "REFUSED" in result.stdout


def test_cli_refuses_climbing_candidate():
    result = _run_cli("--allow", "src", "../secret")
    assert result.returncode != 0
    assert "REFUSED" in result.stdout


def test_cli_refuses_bad_declared_root():
    result = _run_cli("--allow", "/etc", "src/loader.py")
    assert result.returncode != 0
