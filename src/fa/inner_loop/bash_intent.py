"""IntentGuard-specific bash effect analysis.

This module answers a different question from the sandbox classifier in
:mod:`fa.sandbox.classifier`.

- The sandbox classifier asks: "is this command dangerous / package-install /
  generally write-capable from a host-safety perspective?"
- This module asks: "does this command require a trusted current-session
  PR draft before execution, and can we deterministically project any
  intent-relevant repo paths?"

The distinction matters. Commands such as ``pytest`` or ``python -m pytest``
may create caches but are still verification-oriented for the harness; they
must not be blocked by the PR-draft gate. Conversely, opaque execution forms
such as ``python -c ...`` or ``make build`` must require a draft even though
we cannot safely infer their touched paths.

The analyzer is intentionally conservative about what it claims to understand:
unsupported shell features or ambiguous argv shapes fall back to
:class:`BashIntentEffect.OPAQUE_EXEC`, never to a fake path projection.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import bashlex  # type: ignore[import-untyped]

from fa.hygiene.pr_intent import StagedPath

__all__ = [
    "BashIntentAnalysis",
    "BashIntentEffect",
    "analyze_bash_for_intent",
]


class BashIntentEffect(StrEnum):
    READ_ONLY = "read_only"
    VERIFY_ONLY = "verify_only"
    INDEX_WRITE = "index_write"
    REPO_WRITE = "repo_write"
    OPAQUE_EXEC = "opaque_exec"


@dataclass(frozen=True)
class BashIntentAnalysis:
    effect: BashIntentEffect
    projected: tuple[StagedPath, ...] = ()
    reasons: tuple[str, ...] = ()


_WRITE_REDIRECT_TYPES: frozenset[str] = frozenset({">", ">>", ">|", "&>", "&>>", "<>"})
_READ_ONLY_COMMANDS: frozenset[str] = frozenset(
    {
        "ls",
        "cat",
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "find",
        "head",
        "tail",
        "wc",
        "stat",
        "file",
        "du",
        "df",
        "which",
        "whereis",
        "whoami",
        "id",
        "pwd",
        "echo",
        "printf",
        "date",
        "uname",
        "hostname",
        "tree",
        "less",
        "more",
        "diff",
        "cmp",
    }
)
_GIT_READ_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "blame",
        "rev-parse",
        "ls-files",
    }
)
_OPAQUE_HEADS: frozenset[str] = frozenset({"make", "npm", "pnpm", "yarn", "tox", "nox"})
_LITERAL_PATH_META_CHARS: frozenset[str] = frozenset({"*", "?", "[", "]", "{", "}", "$", "~", "`"})
_SED_FLAGS_WITH_VALUE: frozenset[str] = frozenset({"-e", "-f", "--expression", "--file"})
_VERIFY_ONLY_INTERPRETERS: frozenset[str] = frozenset({"python", "python3"})
_RUFF_MUTATING_FLAGS: frozenset[str] = frozenset({"--fix", "--unsafe-fixes"})


def analyze_bash_for_intent(command: str, *, repo_root: Path) -> BashIntentAnalysis:
    """Classify ``command`` for IntentGuard.

    Parse failures and unsupported AST forms deliberately fall back to
    :class:`BashIntentEffect.OPAQUE_EXEC`: the caller may still require a
    trusted draft before execution, but no touched-path claims are made.
    """

    try:
        roots = bashlex.parse(command)
    except Exception as exc:
        return BashIntentAnalysis(
            effect=BashIntentEffect.OPAQUE_EXEC,
            reasons=(f"bash parse failed: {type(exc).__name__}",),
        )
    analyses = tuple(_analyze_node(root, repo_root.resolve()) for root in roots)
    return _reduce_analyses(analyses)


def _analyze_node(node: Any, repo_root: Path) -> BashIntentAnalysis:
    kind = getattr(node, "kind", "")
    if kind == "command":
        return _analyze_command(node, repo_root)
    if kind == "list":
        children = tuple(
            _analyze_node(part, repo_root)
            for part in getattr(node, "parts", [])
            if getattr(part, "kind", "") not in {"operator", "reservedword"}
        )
        if not children:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("empty list",))
        return _reduce_analyses(children)
    if kind == "pipeline":
        children = tuple(
            _analyze_node(part, repo_root)
            for part in getattr(node, "parts", [])
            if getattr(part, "kind", "") not in {"pipe"}
        )
        if not children:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("empty pipeline",))
        return _reduce_analyses(children)
    # Unsupported shell constructs stay opaque by design.
    return BashIntentAnalysis(
        effect=BashIntentEffect.OPAQUE_EXEC,
        reasons=(f"unsupported node kind: {kind or type(node).__name__}",),
    )


def _reduce_analyses(analyses: tuple[BashIntentAnalysis, ...]) -> BashIntentAnalysis:
    if not analyses:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("no analyzable clauses",))

    projected: list[StagedPath] = []
    reasons: list[str] = []
    effects = {analysis.effect for analysis in analyses}
    for analysis in analyses:
        reasons.extend(analysis.reasons)
        if analysis.effect is BashIntentEffect.REPO_WRITE:
            projected.extend(analysis.projected)

    if BashIntentEffect.OPAQUE_EXEC in effects:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=tuple(reasons))

    if BashIntentEffect.INDEX_WRITE in effects and (
        BashIntentEffect.REPO_WRITE in effects or BashIntentEffect.OPAQUE_EXEC in effects
    ):
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=tuple([*reasons, "index-write mixed with non-index mutation"]),
        )

    if BashIntentEffect.REPO_WRITE in effects:
        return BashIntentAnalysis(
            BashIntentEffect.REPO_WRITE,
            projected=tuple(_dedupe_projected(projected)),
            reasons=tuple(reasons),
        )
    if BashIntentEffect.INDEX_WRITE in effects:
        return BashIntentAnalysis(BashIntentEffect.INDEX_WRITE, reasons=tuple(reasons))
    if BashIntentEffect.VERIFY_ONLY in effects:
        return BashIntentAnalysis(BashIntentEffect.VERIFY_ONLY, reasons=tuple(reasons))
    return BashIntentAnalysis(BashIntentEffect.READ_ONLY, reasons=tuple(reasons))


def _dedupe_projected(projected: Iterable[StagedPath]) -> tuple[StagedPath, ...]:
    seen: set[str] = set()
    unique: list[StagedPath] = []
    for entry in projected:
        if entry.path in seen:
            continue
        seen.add(entry.path)
        unique.append(entry)
    return tuple(unique)



def _unwrap_env(words: list[str]) -> list[str] | None:
    args = words[1:]
    while args and (args[0].startswith("-") or _looks_like_assignment(args[0])):
        args = args[1:]
    if not args:
        return None
    return args


def _is_python_interpreter(command_word: str) -> bool:
    return command_word in _VERIFY_ONLY_INTERPRETERS


def _is_verify_only(words: list[str]) -> bool:
    command_word = words[0]
    if command_word == "pytest":
        return True
    if command_word == "mypy":
        return True
    if command_word == "ruff":
        if len(words) >= 2 and words[1] == "check":
            return not any(flag in words[2:] for flag in _RUFF_MUTATING_FLAGS)
        if len(words) >= 3 and words[1] == "format" and "--check" in words[2:]:
            return True
    return False


def _is_read_only(words: list[str]) -> bool:
    head = Path(words[0]).name
    return head in _READ_ONLY_COMMANDS


def _non_flag_args(args: list[str]) -> list[str]:
    result: list[str] = []
    passthrough = False
    for arg in args:
        if passthrough:
            result.append(arg)
            continue
        if arg == "--":
            passthrough = True
            continue
        if arg.startswith("-"):
            continue
        result.append(arg)
    return result


def _sed_target_files(args: list[str]) -> list[str]:
    words = list(args)
    index = 0
    saw_script = False
    while index < len(words):
        flag = words[index]
        if flag == "--":
            index += 1
            break
        if not flag.startswith("-"):
            break
        if flag in _SED_FLAGS_WITH_VALUE:
            saw_script = saw_script or flag in {"-e", "--expression", "-f", "--file"}
            index += 2
            continue
        # `-i` / `-i.bak` are in-place markers. We intentionally do not
        # try to distinguish every backup-suffix form here; when the
        # remaining argv is too ambiguous the caller falls back to OPAQUE.
        index += 1
    if index >= len(words):
        return []
    if saw_script:
        return words[index:]
    # First remaining non-option token is the script expression.
    return words[index + 1 :]


def _perl_target_files(args: list[str]) -> list[str]:
    words = list(args)
    index = 0
    while index < len(words):
        flag = words[index]
        if not flag.startswith("-"):
            break
        if flag in {"-e", "-f"}:
            index += 2
            continue
        index += 1
    return [word for word in words[index:] if not word.startswith("-")]


def _analyze_command(node: Any, repo_root: Path) -> BashIntentAnalysis:
    words: list[str] = []
    redirects: list[Any] = []

    for part in getattr(node, "parts", []):
        kind = getattr(part, "kind", "")
        if kind == "word":
            if getattr(part, "parts", []):
                return BashIntentAnalysis(
                    BashIntentEffect.OPAQUE_EXEC,
                    reasons=(f"word expansion in {getattr(part, 'word', '')!r}",),
                )
            words.append(str(getattr(part, "word", "")))
            continue
        if kind == "assignment":
            if getattr(part, "parts", []):
                return BashIntentAnalysis(
                    BashIntentEffect.OPAQUE_EXEC,
                    reasons=(f"assignment expansion in {getattr(part, 'word', '')!r}",),
                )
            continue
        if kind == "redirect":
            redirects.append(part)
            continue
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=(f"unsupported command part kind: {kind or type(part).__name__}",),
        )

    redirect_projection, has_write_redirect, ambiguous_write_redirect = _analyze_redirects(
        redirects, repo_root
    )
    if not words:
        if ambiguous_write_redirect:
            return BashIntentAnalysis(
                BashIntentEffect.OPAQUE_EXEC,
                reasons=("redirect-only command with ambiguous target",),
            )
        if has_write_redirect:
            return BashIntentAnalysis(
                BashIntentEffect.REPO_WRITE,
                projected=redirect_projection,
                reasons=("redirect-only command",),
            )
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("command without argv",))

    head_raw = words[0]
    head = Path(head_raw).name
    if head == "env":
        wrapped = _unwrap_env(words)
        if wrapped is None:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("env without subcommand",))
        return _analyze_literal_words(
            wrapped,
            redirect_projection=redirect_projection,
            has_write_redirect=has_write_redirect,
            ambiguous_write_redirect=ambiguous_write_redirect,
            repo_root=repo_root,
        )

    return _analyze_literal_words(
        words,
        redirect_projection=redirect_projection,
        has_write_redirect=has_write_redirect,
        ambiguous_write_redirect=ambiguous_write_redirect,
        repo_root=repo_root,
    )


def _analyze_literal_words(
    words: list[str],
    *,
    redirect_projection: tuple[StagedPath, ...],
    has_write_redirect: bool,
    ambiguous_write_redirect: bool,
    repo_root: Path,
) -> BashIntentAnalysis:
    head_raw = words[0]
    head = Path(head_raw).name

    if _is_python_interpreter(head_raw):
        return _analyze_python(
            words,
            redirect_projection=redirect_projection,
            has_write_redirect=has_write_redirect,
            ambiguous_write_redirect=ambiguous_write_redirect,
        )
    if head in {"bash", "sh", "zsh", "dash"}:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=(f"opaque shell exec: {head}",))
    if head in _OPAQUE_HEADS:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=(f"opaque exec family: {head}",))

    git_analysis = _analyze_git(
        words,
        redirect_projection=redirect_projection,
        has_write_redirect=has_write_redirect,
        ambiguous_write_redirect=ambiguous_write_redirect,
    )
    if git_analysis is not None:
        return git_analysis

    if _is_verify_only(words):
        if ambiguous_write_redirect:
            return BashIntentAnalysis(
                BashIntentEffect.OPAQUE_EXEC,
                reasons=(f"verify command with ambiguous write redirection: {head}",),
            )
        if has_write_redirect:
            return BashIntentAnalysis(
                BashIntentEffect.REPO_WRITE,
                projected=redirect_projection,
                reasons=(f"verify command with write redirection: {head}",),
            )
        return BashIntentAnalysis(BashIntentEffect.VERIFY_ONLY, reasons=(f"verify command: {head}",))

    if _is_read_only(words):
        if ambiguous_write_redirect:
            return BashIntentAnalysis(
                BashIntentEffect.OPAQUE_EXEC,
                reasons=(f"read command with ambiguous write redirection: {head}",),
            )
        if has_write_redirect:
            return BashIntentAnalysis(
                BashIntentEffect.REPO_WRITE,
                projected=redirect_projection,
                reasons=(f"read command with write redirection: {head}",),
            )
        return BashIntentAnalysis(BashIntentEffect.READ_ONLY, reasons=(f"read-only command: {head}",))

    repo_write = _analyze_repo_write_command(words, redirect_projection, repo_root)
    if repo_write is not None:
        return repo_write

    if ambiguous_write_redirect or has_write_redirect:
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=(f"unsupported command with write redirection: {head}",),
        )

    return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=(f"unsupported literal command: {head}",))


def _analyze_git(
    words: list[str],
    *,
    redirect_projection: tuple[StagedPath, ...],
    has_write_redirect: bool,
    ambiguous_write_redirect: bool,
) -> BashIntentAnalysis | None:
    if Path(words[0]).name != "git":
        return None
    if len(words) < 2:
        return BashIntentAnalysis(BashIntentEffect.READ_ONLY, reasons=("git without subcommand",))
    subcommand = words[1]
    if ambiguous_write_redirect or has_write_redirect:
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=(f"git {subcommand} with write redirection",),
        )
    if subcommand in {"add", "commit"}:
        return BashIntentAnalysis(BashIntentEffect.INDEX_WRITE, reasons=(f"git {subcommand}",))
    if subcommand in _GIT_READ_SUBCOMMANDS:
        return BashIntentAnalysis(BashIntentEffect.READ_ONLY, reasons=(f"git {subcommand}",))
    return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=(f"git {subcommand}",))


def _analyze_python(
    words: list[str],
    *,
    redirect_projection: tuple[StagedPath, ...],
    has_write_redirect: bool,
    ambiguous_write_redirect: bool,
) -> BashIntentAnalysis:
    if len(words) >= 3 and words[1] == "-m":
        module = words[2]
        if module == "pytest":
            if ambiguous_write_redirect:
                return BashIntentAnalysis(
                    BashIntentEffect.OPAQUE_EXEC,
                    reasons=("python -m pytest with ambiguous write redirection",),
                )
            if has_write_redirect:
                return BashIntentAnalysis(
                    BashIntentEffect.REPO_WRITE,
                    projected=redirect_projection,
                    reasons=("python -m pytest with write redirection",),
                )
            return BashIntentAnalysis(BashIntentEffect.VERIFY_ONLY, reasons=("python -m pytest",))
        if module == "mypy":
            if ambiguous_write_redirect:
                return BashIntentAnalysis(
                    BashIntentEffect.OPAQUE_EXEC,
                    reasons=("python -m mypy with ambiguous write redirection",),
                )
            if has_write_redirect:
                return BashIntentAnalysis(
                    BashIntentEffect.REPO_WRITE,
                    projected=redirect_projection,
                    reasons=("python -m mypy with write redirection",),
                )
            return BashIntentAnalysis(BashIntentEffect.VERIFY_ONLY, reasons=("python -m mypy",))
        if module == "ruff" and len(words) >= 4:
            subcommand = words[3]
            if subcommand == "check":
                if any(flag in words[4:] for flag in _RUFF_MUTATING_FLAGS):
                    return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("python -m ruff check with mutating flags",))
                if ambiguous_write_redirect:
                    return BashIntentAnalysis(
                        BashIntentEffect.OPAQUE_EXEC,
                        reasons=("python -m ruff check with ambiguous write redirection",),
                    )
                if has_write_redirect:
                    return BashIntentAnalysis(
                        BashIntentEffect.REPO_WRITE,
                        projected=redirect_projection,
                        reasons=("python -m ruff check with write redirection",),
                    )
                return BashIntentAnalysis(BashIntentEffect.VERIFY_ONLY, reasons=("python -m ruff check",))
            if subcommand == "format" and "--check" in words[4:]:
                if ambiguous_write_redirect:
                    return BashIntentAnalysis(
                        BashIntentEffect.OPAQUE_EXEC,
                        reasons=("python -m ruff format --check with ambiguous write redirection",),
                    )
                if has_write_redirect:
                    return BashIntentAnalysis(
                        BashIntentEffect.REPO_WRITE,
                        projected=redirect_projection,
                        reasons=("python -m ruff format --check with write redirection",),
                    )
                return BashIntentAnalysis(
                    BashIntentEffect.VERIFY_ONLY,
                    reasons=("python -m ruff format --check",),
                )
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=(f"python -m {module}",))
    if len(words) >= 2 and words[1] == "-c":
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("python -c",))
    return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("python executable",))


def _analyze_repo_write_command(
    words: list[str],
    redirect_projection: tuple[StagedPath, ...],
    repo_root: Path,
) -> BashIntentAnalysis | None:
    head = Path(words[0]).name
    if head == "tee":
        return _analyze_tee(words, redirect_projection, repo_root)
    if head == "touch":
        targets = _non_flag_args(words[1:])
        if not targets:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("touch without targets",))
        projected = tuple(
            entry
            for entry in (_project_path(word, repo_root, delete=False) for word in targets)
            if entry is not None
        )
        if not projected:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("touch targets not literal",))
        return BashIntentAnalysis(
            BashIntentEffect.REPO_WRITE,
            projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
            reasons=("touch",),
        )
    if head == "mkdir":
        targets = _non_flag_args(words[1:])
        if not targets:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("mkdir without targets",))
        projected = tuple(
            entry
            for entry in (_project_path(word, repo_root, delete=False, directory_hint=True) for word in targets)
            if entry is not None
        )
        if not projected:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("mkdir targets not literal",))
        return BashIntentAnalysis(
            BashIntentEffect.REPO_WRITE,
            projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
            reasons=("mkdir",),
        )
    if head == "rm":
        targets = _non_flag_args(words[1:])
        if not targets:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("rm without targets",))
        projected = tuple(
            entry for entry in (_project_path(word, repo_root, delete=True) for word in targets) if entry
        )
        if not projected:
            return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("rm targets not literal",))
        return BashIntentAnalysis(
            BashIntentEffect.REPO_WRITE,
            projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
            reasons=("rm",),
        )
    if head == "cp":
        return _analyze_copy_like(words, repo_root, redirect_projection, delete_source=False)
    if head == "mv":
        return _analyze_copy_like(words, repo_root, redirect_projection, delete_source=True)
    if head == "sed":
        return _analyze_sed(words, repo_root, redirect_projection)
    if head == "perl":
        return _analyze_perl(words, repo_root, redirect_projection)
    return None


def _analyze_tee(
    words: list[str],
    redirect_projection: tuple[StagedPath, ...],
    repo_root: Path,
) -> BashIntentAnalysis:
    targets = _non_flag_args(words[1:])
    if not targets:
        if redirect_projection:
            return BashIntentAnalysis(
                BashIntentEffect.REPO_WRITE,
                projected=redirect_projection,
                reasons=("tee with write redirection",),
            )
        return BashIntentAnalysis(BashIntentEffect.READ_ONLY, reasons=("tee to stdout",))
    projected = tuple(
        entry for entry in (_project_path(word, repo_root, delete=False) for word in targets) if entry
    )
    if not projected:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("tee targets not literal",))
    return BashIntentAnalysis(
        BashIntentEffect.REPO_WRITE,
        projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
        reasons=("tee",),
    )


def _analyze_copy_like(
    words: list[str],
    repo_root: Path,
    redirect_projection: tuple[StagedPath, ...],
    *,
    delete_source: bool,
) -> BashIntentAnalysis:
    args = list(words[1:])
    while args and args[0].startswith("-"):
        args.pop(0)
    if len(args) != 2:
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=(("mv" if delete_source else "cp") + " requires exactly one src and one dst",),
        )
    src_raw, dst_raw = args
    src = _project_path(src_raw, repo_root, delete=delete_source)
    dst = _project_path(dst_raw, repo_root, delete=False)
    if src is None or dst is None:
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=(("mv" if delete_source else "cp") + " args not literal",),
        )
    if dst.path.endswith("/"):
        return BashIntentAnalysis(
            BashIntentEffect.OPAQUE_EXEC,
            reasons=(("mv" if delete_source else "cp") + " destination directory is ambiguous",),
        )
    projected = [dst]
    if delete_source:
        projected.insert(0, src)
    return BashIntentAnalysis(
        BashIntentEffect.REPO_WRITE,
        projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
        reasons=(("mv" if delete_source else "cp"),),
    )


def _analyze_sed(
    words: list[str],
    repo_root: Path,
    redirect_projection: tuple[StagedPath, ...],
) -> BashIntentAnalysis | None:
    args = words[1:]
    in_place = any(arg == "-i" or arg.startswith("-i") for arg in args)
    if not in_place:
        return None
    files = _sed_target_files(args)
    if not files:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("sed -i without literal files",))
    projected = tuple(
        entry
        for entry in (_project_path(word, repo_root, delete=False, force_modify=True) for word in files)
        if entry
    )
    if not projected:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("sed -i files not literal",))
    return BashIntentAnalysis(
        BashIntentEffect.REPO_WRITE,
        projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
        reasons=("sed -i",),
    )


def _analyze_perl(
    words: list[str],
    repo_root: Path,
    redirect_projection: tuple[StagedPath, ...],
) -> BashIntentAnalysis | None:
    args = words[1:]
    if not any(arg.startswith("-pi") or arg == "-i" for arg in args):
        return None
    files = _perl_target_files(args)
    if not files:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("perl -pi without literal files",))
    projected = tuple(
        entry
        for entry in (_project_path(word, repo_root, delete=False, force_modify=True) for word in files)
        if entry
    )
    if not projected:
        return BashIntentAnalysis(BashIntentEffect.OPAQUE_EXEC, reasons=("perl -pi files not literal",))
    return BashIntentAnalysis(
        BashIntentEffect.REPO_WRITE,
        projected=tuple(_dedupe_projected([*projected, *redirect_projection])),
        reasons=("perl -pi",),
    )


def _analyze_redirects(
    redirects: Iterable[Any],
    repo_root: Path,
) -> tuple[tuple[StagedPath, ...], bool, bool]:
    projected: list[StagedPath] = []
    has_write_redirect = False
    ambiguous_write_redirect = False
    for redirect in redirects:
        redirect_type = str(getattr(redirect, "type", ""))
        if redirect_type not in _WRITE_REDIRECT_TYPES:
            continue
        output = getattr(redirect, "output", None)
        if output is None or getattr(output, "kind", "") != "word" or getattr(output, "parts", []):
            ambiguous_write_redirect = True
            has_write_redirect = True
            continue
        raw = str(getattr(output, "word", ""))
        if not raw or any(char in raw for char in _LITERAL_PATH_META_CHARS):
            ambiguous_write_redirect = True
            has_write_redirect = True
            continue
        path = _project_path(raw, repo_root, delete=False)
        if path is None:
            # Literal sink outside the repo (``/dev/null``, ``/tmp/log``) is
            # intent-irrelevant. It should not force a draft on otherwise
            # read-only / verify-only commands.
            continue
        has_write_redirect = True
        projected.append(path)
    return tuple(_dedupe_projected(projected)), has_write_redirect, ambiguous_write_redirect


def _project_path(
    raw: str,
    repo_root: Path,
    *,
    delete: bool,
    directory_hint: bool = False,
    force_modify: bool = False,
) -> StagedPath | None:
    if not raw or any(char in raw for char in _LITERAL_PATH_META_CHARS):
        return None
    repo_root_resolved = repo_root.resolve()
    candidate = (repo_root_resolved / Path(raw)).resolve()
    try:
        rel = candidate.relative_to(repo_root_resolved)
    except ValueError:
        return None
    rel_text = str(rel).replace("\\", "/")
    is_dir = directory_hint or raw.endswith("/") or candidate.is_dir()
    if is_dir and rel_text and not rel_text.endswith("/"):
        rel_text += "/"
    if delete:
        return StagedPath(status="D", path=rel_text)
    if force_modify:
        return StagedPath(status="M", path=rel_text)
    return StagedPath(status="M" if candidate.exists() else "A", path=rel_text)


def _looks_like_assignment(token: str) -> bool:
    if "=" not in token:
        return False
    key, _value = token.split("=", 1)
    return bool(key) and key.replace("_", "a").isalnum()
