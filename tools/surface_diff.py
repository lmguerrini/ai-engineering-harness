"""AST-based description of Python names callers can observe and rely upon.

The five categories this reports are added and removed public names, added and
removed public methods, changed signatures, changed return annotations, and a
private name imported across a module boundary. The CLI additionally infers
*relocation*: a public name that disappears from one module and appears under
the same name in another module between the same two refs is reported as
relocated rather than as an unrelated add and remove.

Three properties are load-bearing and were each absent at some point:

*   **Calling convention is part of a signature.** ``def f(a, b)`` and
    ``def f(a, *, b)`` accept different calls. Flattening parameters into one
    list made every caller of ``f(1, 2)`` breakable with the gate reporting
    nothing, which is the plainest possible missed signature change.
*   **A name is public if callers can import it**, not only if it is defined
    here. A re-export and an ``__all__`` entry are both names other code binds
    to, so both are part of the surface.
*   **Reformatting is not a change.** Annotations are compared as parsed
    structure, not as source text, so ``int|None`` becoming ``int | None`` and
    a quoted annotation becoming unquoted are correctly silent.

HONEST GAP, carried forward rather than papered over: class-level attributes,
dataclass field types, base classes and nested classes are NOT compared. Those
are real parts of a contract, and their absence is a gap in the categories
above rather than a deliberate exclusion — the gap is named here, in
``--help``, and pinned by a test that asserts it stays undetected, so a silent
report is never read as a clean one.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field

import gitread
from errors import IntegrityError

__all__ = [
    "Parameter", "Signature", "PublicClass", "Surface", "SurfaceChange",
    "surface", "compare",
]

_INVARIANTS = (
    "A private name imported across a module boundary is a reported surface change.",
    "A parameter's calling convention is part of the signature, not a detail below it.",
    "Reformatting an annotation is not a surface change.",
)

#: How a parameter may be passed. Two signatures with the same parameter names
#: in the same order but different kinds accept different calls.
POSITIONAL_ONLY = "positional_only"
POSITIONAL_OR_KEYWORD = "positional_or_keyword"
VAR_POSITIONAL = "var_positional"
KEYWORD_ONLY = "keyword_only"
VAR_KEYWORD = "var_keyword"


@dataclass(frozen=True)
class Parameter:
    name: str
    kind: str
    has_default: bool
    default: str | None = None
    annotation: str | None = None


@dataclass(frozen=True)
class Signature:
    parameters: tuple[Parameter, ...]
    return_annotation: str | None
    is_async: bool = False
    #: Decorators change how a name is used — a method becoming a property
    #: stops being callable — so they belong to the signature a caller relies
    #: on.
    decorators: tuple[str, ...] = ()


@dataclass(frozen=True)
class PublicClass:
    methods: dict[str, Signature]


@dataclass(frozen=True)
class Surface:
    module_name: str
    public_names: frozenset[str]
    functions: dict[str, Signature]
    classes: dict[str, PublicClass]
    private_imports: frozenset[str]
    #: The module's declared star-export, or ``None`` when it declares none.
    #: Empty and absent are different facts.
    exported_names: frozenset[str] | None = None


@dataclass(frozen=True)
class SurfaceChange:
    kind: str
    name: str


def _normalise_annotation(node: ast.expr | None) -> str | None:
    """An annotation or default as structure, not as the text someone typed.

    Comparing ``ast.get_source_segment`` output made a formatter's whitespace
    and a quoted forward reference read as contract changes. Unparsing both
    sides normalises them.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            inner = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return node.value
        return ast.unparse(inner)
    return ast.unparse(node)


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Signature:
    args = node.args
    parameters: list[Parameter] = []

    positional_defaults: list[ast.expr | None] = [None] * (
        len(args.posonlyargs) + len(args.args) - len(args.defaults)
    ) + list(args.defaults)
    positional = [(argument, POSITIONAL_ONLY) for argument in args.posonlyargs]
    positional += [(argument, POSITIONAL_OR_KEYWORD) for argument in args.args]
    for (argument, kind), default in zip(positional, positional_defaults):
        parameters.append(
            Parameter(argument.arg, kind, default is not None, _normalise_annotation(default), _normalise_annotation(argument.annotation))
        )
    if args.vararg is not None:
        parameters.append(
            Parameter(args.vararg.arg, VAR_POSITIONAL, False, None, _normalise_annotation(args.vararg.annotation))
        )
    for argument, default in zip(args.kwonlyargs, args.kw_defaults):
        parameters.append(
            Parameter(argument.arg, KEYWORD_ONLY, default is not None, _normalise_annotation(default), _normalise_annotation(argument.annotation))
        )
    if args.kwarg is not None:
        parameters.append(Parameter(args.kwarg.arg, VAR_KEYWORD, False, None, _normalise_annotation(args.kwarg.annotation)))
    return Signature(
        tuple(parameters),
        _normalise_annotation(node.returns),
        isinstance(node, ast.AsyncFunctionDef),
        tuple(sorted(ast.unparse(decorator) for decorator in node.decorator_list)),
    )


def _assigned_names(node: ast.stmt) -> set[str]:
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    elif isinstance(node, ast.AugAssign):
        targets.append(node.target)
    names: set[str] = set()
    for target in targets:
        for item in ast.walk(target):
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
                names.add(item.id)
    return names


def _declared_exports(node: ast.stmt) -> frozenset[str] | None:
    """The names in an ``__all__ = [...]`` assignment, if this is one."""
    if not isinstance(node, ast.Assign):
        return None
    if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
        return None
    if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
        return None
    return frozenset(
        element.value
        for element in node.value.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    )


def _module_level(body: list[ast.stmt]) -> list[ast.stmt]:
    """Statements that define module-level names, including conditional ones.

    A public function under ``if sys.version_info >= ...`` or inside a
    ``try``/``except ImportError`` is bound at module level and importable.
    Iterating ``tree.body`` alone made every such definition invisible to the
    detector.
    """
    flat: list[ast.stmt] = []
    for node in body:
        flat.append(node)
        if isinstance(node, ast.If):
            flat.extend(_module_level(node.body))
            flat.extend(_module_level(node.orelse))
        elif isinstance(node, ast.Try):
            flat.extend(_module_level(node.body))
            flat.extend(_module_level(node.orelse))
            flat.extend(_module_level(node.finalbody))
            for handler in node.handlers:
                flat.extend(_module_level(handler.body))
        elif isinstance(node, ast.With):
            flat.extend(_module_level(node.body))
        elif isinstance(node, (ast.For, ast.While)):
            flat.extend(_module_level(node.body))
            flat.extend(_module_level(node.orelse))
        elif isinstance(node, ast.Match):
            for case in node.cases:
                flat.extend(_module_level(case.body))
    return flat


def surface(source: str, module_name: str) -> Surface:
    """Extract the public contract and cross-module private imports of one module."""
    try:
        tree = ast.parse(source, filename=module_name)
    except (SyntaxError, ValueError) as exc:
        # A file that will not parse is a real thing a worker can produce.
        # Letting the parser's own exception escape breaks "a refusal names
        # its cause" and leaves the caller unable to tell a broken patch from
        # a broken gate.
        raise IntegrityError(
            "source cannot be parsed for public-surface comparison",
            module=module_name,
            error=str(exc),
        ) from exc
    public_names: set[str] = set()
    functions: dict[str, Signature] = {}
    classes: dict[str, PublicClass] = {}
    private_imports: set[str] = set()
    re_exports: set[tuple[str, str]] = set()
    exported_names: frozenset[str] | None = None

    for node in _module_level(tree.body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                public_names.add(node.name)
                functions[node.name] = _signature(node)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                public_names.add(node.name)
                methods = {
                    method.name: _signature(method)
                    for method in node.body
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and not method.name.startswith("_")
                }
                classes[node.name] = PublicClass(methods)
        elif isinstance(node, ast.ImportFrom) and (node.module is not None or node.level > 0):
            origin = "." * node.level + (node.module or "")
            for imported in node.names:
                if imported.name.startswith("_"):
                    separator = "" if origin.endswith(".") else "."
                    private_imports.add(f"{origin}{separator}{imported.name}")
                    continue
                bound = imported.asname or imported.name
                if not bound.startswith("_"):
                    re_exports.add((origin, bound))
        elif isinstance(node, ast.Import):
            for imported in node.names:
                # `import package._internal` reaches across a module boundary
                # into a private name just as `from package import _internal`
                # does; only the syntax differs.
                if any(part.startswith("_") for part in imported.name.split(".")):
                    private_imports.add(imported.name)
        else:
            declared = _declared_exports(node)
            if declared is not None:
                exported_names = declared
            public_names.update(name for name in _assigned_names(node) if not name.startswith("_"))
    # An imported name is part of the surface only when it was imported *to
    # be* part of it: a relative import, which is the package-internal
    # re-export idiom, or a name the module lists in `__all__`.
    for origin, bound in re_exports:
        if origin.startswith(".") or (exported_names is not None and bound in exported_names):
            public_names.add(bound)

    return Surface(
        module_name,
        frozenset(public_names),
        functions,
        classes,
        frozenset(private_imports),
        exported_names,
    )


def _qualified(module: str, *parts: str) -> str:
    return ".".join((module, *parts))


def compare(before: Surface, after: Surface) -> list[SurfaceChange]:
    """Return deterministic, caller-visible changes from one module revision to another."""
    module = after.module_name
    changes: list[SurfaceChange] = []
    for name in sorted(after.public_names - before.public_names):
        changes.append(SurfaceChange("added_public_name", _qualified(module, name)))
    for name in sorted(before.public_names - after.public_names):
        changes.append(SurfaceChange("removed_public_name", _qualified(module, name)))

    # `__all__` decides what `from module import *` binds, so shrinking it
    # removes names callers can rely on even though every definition remains.
    prior_exports = before.exported_names
    current_exports = after.exported_names
    if prior_exports != current_exports:
        if prior_exports is None or current_exports is None:
            changes.append(SurfaceChange("changed_star_export", _qualified(module, "__all__")))
        else:
            for name in sorted(current_exports - prior_exports):
                changes.append(SurfaceChange("added_star_export", _qualified(module, name)))
            for name in sorted(prior_exports - current_exports):
                changes.append(SurfaceChange("removed_star_export", _qualified(module, name)))

    for class_name in sorted(set(before.classes) & set(after.classes)):
        prior = before.classes[class_name].methods
        current = after.classes[class_name].methods
        for method in sorted(current.keys() - prior.keys()):
            changes.append(SurfaceChange("added_public_method", _qualified(module, class_name, method)))
        for method in sorted(prior.keys() - current.keys()):
            changes.append(SurfaceChange("removed_public_method", _qualified(module, class_name, method)))
        for method in sorted(prior.keys() & current.keys()):
            _compare_signature(changes, _qualified(module, class_name, method), prior[method], current[method])
    for function in sorted(set(before.functions) & set(after.functions)):
        _compare_signature(changes, _qualified(module, function), before.functions[function], after.functions[function])
    for imported in sorted(after.private_imports - before.private_imports):
        changes.append(SurfaceChange("private_name_exported", imported))
    return changes


def _compare_signature(changes: list[SurfaceChange], name: str, before: Signature, after: Signature) -> None:
    if (
        before.parameters != after.parameters
        or before.is_async != after.is_async
        or before.decorators != after.decorators
    ):
        changes.append(SurfaceChange("changed_signature", name))
    if before.return_annotation != after.return_annotation:
        changes.append(SurfaceChange("changed_return_annotation", name))


def _module_name(path: str) -> str:
    return path[:-3].replace("/", ".") if path.endswith(".py") else path.replace("/", ".")


def _python_files_at(repository: str, ref: str) -> list[str]:
    output = gitread._run(repository, "ls-tree", "-r", "--name-only", ref)
    return sorted(line for line in str(output).splitlines() if line.endswith(".py"))


def _read_source(repository: str, ref: str, path: str) -> str:
    raw = gitread._run(repository, "show", f"{ref}:{path}", text=False)
    assert isinstance(raw, bytes)
    return raw.decode("utf-8", "surrogateescape")


def diff_refs(
    repository: str, before_ref: str, after_ref: str,
) -> tuple[dict[str, list[SurfaceChange]], list[tuple[str, str, str]]]:
    """Every module's surface changes between two refs, plus inferred relocations.

    Returns ``(changes_by_module, relocations)`` where a relocation is
    ``(name, from_module, to_module)`` for a public name removed from one
    module and added under the same name to a different module.
    """
    before_files = _python_files_at(repository, before_ref)
    after_files = _python_files_at(repository, after_ref)
    common = sorted(set(before_files) & set(after_files))

    changes_by_module: dict[str, list[SurfaceChange]] = {}
    removed_elsewhere: dict[str, str] = {}
    added_elsewhere: dict[str, str] = {}

    for path in common:
        module = _module_name(path)
        before_surface = surface(_read_source(repository, before_ref, path), module)
        after_surface = surface(_read_source(repository, after_ref, path), module)
        module_changes = compare(before_surface, after_surface)
        if module_changes:
            changes_by_module[path] = module_changes
        for name in sorted(before_surface.public_names - after_surface.public_names):
            removed_elsewhere[name] = path
        for name in sorted(after_surface.public_names - before_surface.public_names):
            added_elsewhere[name] = path

    relocations: list[tuple[str, str, str]] = []
    for name in sorted(set(removed_elsewhere) & set(added_elsewhere)):
        from_path = removed_elsewhere[name]
        to_path = added_elsewhere[name]
        if from_path != to_path:
            relocations.append((name, from_path, to_path))

    return changes_by_module, relocations


def _cli(argv: list[str]) -> int:
    """Diff the public surface of a repository between two refs.

    Usage: ``surface_diff.py REPO BEFORE_REF AFTER_REF [--allow-growth NAME ...]``

    Every Python file present at both refs is compared. A public name removed
    from one module and added under the same name to another is reported as
    relocated rather than as an unrelated add and remove. Exits non-zero on
    any unrequested public-name growth (an ``added_public_name`` not named by
    ``--allow-growth``) or any relocation.

    KNOWN GAP: class-level attributes, dataclass field types, base classes and
    nested classes are not compared. A change confined to those is not
    detected by this tool.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="surface_diff.py", description=__doc__.strip().splitlines()[0])
    parser.add_argument("repository")
    parser.add_argument("before_ref")
    parser.add_argument("after_ref")
    parser.add_argument("--allow-growth", action="append", default=[], metavar="NAME", help="a fully-qualified added public name that is expected (repeatable)")
    args = parser.parse_args(argv)

    changes_by_module, relocations = diff_refs(args.repository, args.before_ref, args.after_ref)

    unrequested_growth = False
    for path, changes in sorted(changes_by_module.items()):
        for change in changes:
            print(f"{path}: {change.kind} {change.name}")
            if change.kind == "added_public_name" and change.name not in args.allow_growth:
                unrequested_growth = True
    for name, from_path, to_path in relocations:
        print(f"relocated: {name} ({from_path} -> {to_path})")

    if not changes_by_module and not relocations:
        print("clean: no public-surface changes")

    return 1 if (unrequested_growth or relocations) else 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
