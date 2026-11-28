"""Provenance checker: decides whether a committed provenance manifest proves
a component was already verified against the current spec state."""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

USAGE = (
    "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
    "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]"
)

_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")

_CLI_ID_RE = re.compile(r"(comp-)?[a-z0-9]+(-[a-z0-9]+)*")
_CLI_HASH_RE = re.compile(r"sha256:[0-9a-f]+")

_COMP_RE = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SRC_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?")
_SHA_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VER_RE = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")
_TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}
_CHAR_KEYS = {"overall", "criteria_passed", "criteria_total"}


class ProvenanceCheckResult(dict):
    """A dict that also exposes its keys as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    spec_bundle_parts: dict
    gate_versions: dict
    assets: list
    drivers: list


@dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


# ---------------------------------------------------------------- helpers

def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _slug(component_id):
    return component_id[5:] if component_id.startswith("comp-") else component_id


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load(rel_dir, module, repo_root):
    directory = Path(repo_root) / rel_dir
    if not directory.is_dir():
        directory = _tool_root() / rel_dir
    file_path = directory / f"{module}.py"
    if file_path.is_file():
        spec = importlib.util.spec_from_file_location(module, file_path)
    else:
        package_dir = directory / module
        spec = importlib.util.spec_from_file_location(
            module, package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def _component_md(slug, repo_root):
    return Path(repo_root) / "specs" / "components" / slug / "component.md"


def _frontmatter(path):
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def _fm_value(fm, key):
    prefix = f"{key}:"
    for line in fm:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _parse_list(value):
    if value is None or not (value.startswith("[") and value.endswith("]")):
        return None
    return [item.strip() for item in value[1:-1].split(",") if item.strip()]


def _sealed(fm):
    return fm is not None and any(line.strip() == "sealed: true" for line in fm)


def _is_sealed(slug, repo_root):
    return _sealed(_frontmatter(_component_md(slug, repo_root)))


def _current_env(component_id, repo_root):
    """(ok, failure_message, assets, drivers) for the component (R-PROVCHECK-009)."""
    if _is_sealed(_slug(component_id), repo_root):
        return True, None, [], []
    run_environment = _load("gen/run-environment", "run_environment", repo_root)
    env = run_environment.prepare(component_id, repo_root)
    result = (
        _get(env, "ok"),
        _get(env, "failure_message"),
        _get(env, "assets"),
        _get(env, "drivers"),
    )
    close = _get(env, "close")
    if callable(close):
        close()
    return result


def _as_list(value):
    return [] if value is None else value


def _env_only(recorded, current):
    return (
        isinstance(recorded, list)
        and len(recorded) == len(current)
        and all(
            isinstance(r, dict)
            and set(r) == set(c)
            and all(r[k] == c[k] for k in c if k not in ("versions", "lockfile_sha256"))
            for r, c in zip(recorded, current)
        )
    )


def _env_reason(manifest, env):
    ok, failure_message, assets, drivers = env
    if not ok:
        return failure_message
    recorded_assets = _as_list(manifest.get("assets"))
    recorded_drivers = _as_list(manifest.get("drivers"))
    if recorded_assets != assets:
        reason = "assets differ"
    elif recorded_drivers != drivers:
        reason = "drivers differ"
    else:
        return None
    if _env_only(recorded_assets, assets) and _env_only(recorded_drivers, drivers):
        return "environment differs"
    return reason


def _git(repo_root, *args):
    return subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def _spec_inputs_unchanged(slug, repo_root):
    """R-PROVCHECK-012's git test."""
    manifest_rel = f"gen/{slug}/.provenance.json"
    fm = _frontmatter(_component_md(slug, repo_root)) or []
    deps = _parse_list(_fm_value(fm, "depends_on")) or []
    paths = [
        f"specs/components/{slug}/",
        "specs/architecture/",
        "specs/asset-kinds/",
        "specs/glossary.md",
    ] + [f"specs/components/{_slug(dep)}/interface/" for dep in deps]
    try:
        if (_git(repo_root, "ls-files", "--error-unmatch", "--", manifest_rel).returncode
                or _git(repo_root, "diff", "--quiet", "HEAD", "--", manifest_rel).returncode):
            return False
        log = _git(repo_root, "log", "-1", "--format=%H", "--", manifest_rel)
        if log.returncode:
            return False
        commit = log.stdout.strip()
        return _git(repo_root, "diff", "--quiet", commit, "--", *paths).returncode == 0
    except OSError:
        return False


def _trust_judge():
    return os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "").strip().lower() != "false"


def _has_llm_judge(manifest):
    report = manifest.get("verification_report") or {}
    return any(c.get("kind") == "llm-judge" for c in report.get("criteria") or [])


def _miss(reason):
    return ProvenanceCheckResult(
        hit=False, reason=reason,
        verification_report=None, license_scan=None, secret_scan=None,
    )


# ---------------------------------------------------------------- library

def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root,
                     spec_bundle_parts=None):
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    path = repo_root / "gen" / slug / ".provenance.json"
    if not path.is_file():
        return _miss("no manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))

    recorded = manifest.get("gate_versions") or {}
    differing = {
        k for k in set(recorded) | set(gate_versions)
        if recorded.get(k) != gate_versions.get(k)
    }
    gates_allowed = "generator" not in differing

    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        if gates_allowed:
            env = None
            parts = manifest.get("spec_bundle_parts")
            if (spec_bundle_parts is not None
                    and isinstance(parts, dict)
                    and parts.get("spec") == spec_bundle_parts.get("spec")
                    and parts.get("dependency_code") != spec_bundle_parts.get("dependency_code")):
                env = _current_env(component_id, repo_root)
                if _env_reason(manifest, env) is None:
                    return _miss("dependency code differs")
            if _spec_inputs_unchanged(slug, repo_root):
                if env is None:
                    env = _current_env(component_id, repo_root)
                if _env_reason(manifest, env) in (None, "environment differs"):
                    return _miss("hash formula differs")
        return _miss("spec_bundle_hash differs")

    if differing:
        return _miss("gates differ" if gates_allowed else "gate_versions differ")

    reason = _env_reason(manifest, _current_env(component_id, repo_root))
    if reason is not None:
        return _miss(reason)

    if not _trust_judge() and _has_llm_judge(manifest):
        return _miss("llm-judge results not trusted")

    return ProvenanceCheckResult(
        hit=True, reason=None,
        verification_report=manifest.get("verification_report"),
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id, repo_root):
    repo_root = Path(repo_root)
    assembler = _load("gen/spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    spec_bundle_parts = dict(_get(bundle, "spec_bundle_parts"))

    compiler = _load("pipeline/criterion-compiler", "criterion_compiler", repo_root).GATE_VERSION
    generated_test = _load("gen/test-author", "test_author", repo_root).GATE_VERSION
    verifier = _load("gen/verifier-orchestrator", "verifier_orchestrator", repo_root).GATE_VERSION
    license_version = _load("gen/license-scanner", "license_scanner", repo_root).gate_version(repo_root)
    secret_version = _load("gen/secret-scanner", "secret_scanner", repo_root).gate_version(repo_root)
    generator = _load("gen/generator", "generator", repo_root)
    generator_version = f"{generator.GATE_VERSION}+{generator.PROMPT_VERSION}"

    _, _, assets, drivers = _current_env(component_id, repo_root)

    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash,
        spec_bundle_parts=spec_bundle_parts,
        gate_versions={
            "compiler": compiler,
            "generated_test": generated_test,
            "verifier": verifier,
            "license_scanner": license_version,
            "secret_scanner": secret_version,
            "generator": generator_version,
        },
        assets=list(assets),
        drivers=list(drivers),
    )


def _match(regex, value):
    return isinstance(value, str) and regex.fullmatch(value) is not None


def _valid_owners(value):
    return isinstance(value, list) and bool(value) and all(_match(_OWNER_RE, o) for o in value)


def _valid_source_path(value):
    return _match(_SRC_RE, value) and value.split("/")[0] != "gen"


def _source_hash(base):
    entries = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".sealed-provenance.json":
                full = Path(dirpath) / name
                entries.append((full.relative_to(base).as_posix(), full))
    digest = hashlib.sha256()
    for rel, full in sorted(entries):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(full.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    md = _component_md(_slug(component_id), repo_root)
    fm = _frontmatter(md)
    if not _sealed(fm):
        return None
    owners = _parse_list(_fm_value(fm, "owners"))
    if not _valid_owners(owners):
        raise ValueError(f"{md}: missing or invalid owners")
    source_path = _fm_value(fm, "source_path")
    if not _valid_source_path(source_path):
        raise ValueError(f"{md}: missing or invalid source_path")
    verifier = _load("gen/verifier-orchestrator", "verifier_orchestrator", repo_root)
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=_source_hash(repo_root / source_path),
        verifier_version=verifier.GATE_VERSION,
    )


def _valid_sealed_manifest(m):
    if not isinstance(m, dict) or set(m) != _SEALED_KEYS:
        return False
    ch = m["characterization"]
    if not isinstance(ch, dict) or set(ch) != _CHAR_KEYS:
        return False
    passed, total = ch["criteria_passed"], ch["criteria_total"]
    return (
        m["kind"] == "sealed-provenance"
        and type(m["version"]) is int and m["version"] == 1
        and _match(_COMP_RE, m["component_id"])
        and _valid_owners(m["owners"])
        and _valid_source_path(m["source_path"])
        and _match(_SHA_RE, m["source_hash"])
        and _match(_VER_RE, m["verifier_version"])
        and ch["overall"] in ("pass", "fail")
        and type(passed) is int and type(total) is int
        and 0 <= passed <= total
        and (ch["overall"] != "pass" or (total >= 1 and passed == total))
        and _match(_TIME_RE, m["written_at"])
    )


def _sealed_result(reason, sealed=True, manifest=None):
    hit = reason is None
    return {
        "hit": hit,
        "sealed": sealed,
        "reason": reason,
        "verification_report": {"overall": manifest["characterization"]["overall"]} if hit else None,
        "license_scan": None,
        "secret_scan": None,
        "owners": manifest["owners"] if hit else None,
        "source_hash": manifest["source_hash"] if hit else None,
        "written_at": manifest["written_at"] if hit else None,
    }


def check_sealed_provenance(component_id, repo_root):
    repo_root = Path(repo_root)
    key = current_sealed_key(component_id, repo_root)
    if key is None:
        return _sealed_result("not_sealed", sealed=False)
    path = repo_root / key.source_path / ".sealed-provenance.json"
    if not path.exists():
        return _sealed_result("manifest_missing")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _sealed_result("manifest_invalid")
    if not _valid_sealed_manifest(manifest):
        return _sealed_result("manifest_invalid")
    checks = [
        (manifest["component_id"] != "comp-" + _slug(component_id)
         or manifest["source_path"] != key.source_path, "component_mismatch"),
        (manifest["source_hash"] != key.source_hash, "source_changed"),
        (manifest["owners"] != key.owners, "owners_changed"),
        (manifest["verifier_version"] != key.verifier_version, "verifier_changed"),
        (manifest["characterization"]["overall"] != "pass", "characterization_failed"),
    ]
    reason = next((r for failed, r in checks if failed), None)
    return _sealed_result(reason, manifest=manifest)


# ---------------------------------------------------------------- CLI

def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "check":
        return _usage(f"unknown subcommand: {argv[0]}" if argv else "missing subcommand")

    values = {}
    positionals = []
    i = 1
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in _FLAGS:
            if not eq:
                if i + 1 >= len(argv):
                    return _usage(f"{name} requires a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif token.startswith("-") or positionals:
            return _usage(f"unknown argument: {token}")
        else:
            positionals.append(token)
        i += 1

    if not positionals:
        return _usage("missing <component-id>")
    component_id = positionals[0]
    if not _CLI_ID_RE.fullmatch(component_id):
        return _usage(f"invalid component id: {component_id}")

    spec_bundle_hash = values.get("--spec-bundle-hash")
    if spec_bundle_hash is None:
        return _usage("missing --spec-bundle-hash")
    if not _CLI_HASH_RE.fullmatch(spec_bundle_hash):
        return _usage(f"invalid --spec-bundle-hash: {spec_bundle_hash}")

    gate_text = values.get("--gate-versions")
    if gate_text is None:
        return _usage("missing --gate-versions")
    try:
        gate_versions = json.loads(gate_text)
    except ValueError:
        return _usage("--gate-versions is not valid JSON")
    if not isinstance(gate_versions, dict) or not all(
            isinstance(v, str) for v in gate_versions.values()):
        return _usage("--gate-versions must be a JSON object of strings")

    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format: {fmt}")

    repo_root = Path(values.get("--repo-root", "."))
    result = check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    if fmt == "json":
        print(json.dumps(result))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
