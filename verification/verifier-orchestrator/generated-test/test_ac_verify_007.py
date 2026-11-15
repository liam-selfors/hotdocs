"""AC-VERIFY-007: verify produces exactly one VerificationReport carrying
per-criterion results, mutation_score, interface_drift and overall."""

import dataclasses
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_ASSEMBLER = r'''
import hashlib
from dataclasses import dataclass, field
from pathlib import Path


class _MappingMixin:
    def __getitem__(self, key):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self.__dataclass_fields__)

    def items(self):
        return [(k, getattr(self, k)) for k in self.__dataclass_fields__]

    def values(self):
        return [getattr(self, k) for k in self.__dataclass_fields__]

    def __iter__(self):
        return iter(list(self.__dataclass_fields__))

    def __len__(self):
        return len(self.__dataclass_fields__)

    def __contains__(self, key):
        return key in self.__dataclass_fields__


@dataclass
class SpecBundle(_MappingMixin):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclass
class CriterionBundle(_MappingMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _body(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 4)
            return text[nl + 1:] if nl != -1 else ""
    return text


def _join(texts):
    parts = [t.strip() for t in texts if t.strip()]
    return "\n\n".join(parts)


def _files(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*.md") if p.is_file())


def _comp_dir(component_id, repo_root):
    d = Path(repo_root) / "specs" / "components" / _slug(component_id)
    if not (d / "component.md").is_file():
        raise ValueError("unknown component id: " + component_id)
    return d


def _glossary(repo_root):
    p = Path(repo_root) / "specs" / "glossary.md"
    return p.read_text().strip() if p.is_file() else ""


def assemble(component_id, repo_root, mode="cold"):
    if mode not in ("cold", "hint"):
        raise ValueError("bad mode: " + str(mode))
    d = _comp_dir(component_id, repo_root)
    spec_files = [d / "component.md"] + _files(d / "requirements")
    iface_files = _files(d / "interface")
    constraints_file = d / "constraints.md"
    spec = _join(_body(p.read_text()) for p in spec_files)
    interface = _join(p.read_text() for p in iface_files)
    constraints = constraints_file.read_text().strip() if constraints_file.is_file() else ""
    glossary = _glossary(repo_root)
    h = hashlib.sha256()
    for p in spec_files + iface_files + ([constraints_file] if constraints_file.is_file() else []):
        h.update(str(p.relative_to(repo_root)).encode("utf-8"))
        h.update(p.read_bytes())
    h.update(glossary.encode("utf-8"))
    hint_code = None
    if mode == "hint":
        gen_dir = Path(repo_root) / "gen" / _slug(component_id)
        hint_code = {}
        if gen_dir.is_dir():
            for p in sorted(gen_dir.rglob("*")):
                if p.is_file():
                    hint_code[str(p.relative_to(gen_dir))] = p.read_text()
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + h.hexdigest(),
        spec=spec,
        interface=interface,
        constraints=constraints,
        glossary=glossary,
        hint_code=hint_code,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    d = _comp_dir(component_id, repo_root)
    ac = d / "acceptance" / (criterion_id + ".md")
    if not ac.is_file():
        raise ValueError("unknown criterion id: " + criterion_id)
    text = ac.read_text()
    covers = ""
    for line in text.splitlines():
        if line.startswith("Covers:"):
            covers = line[len("Covers:"):].strip()
            break
    req = d / "requirements" / (covers + ".md")
    requirement_text = req.read_text().strip() if req.is_file() else ""
    interface = _join(p.read_text() for p in _files(d / "interface"))
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=text.strip(),
        requirement_text=requirement_text,
        interface=interface,
        glossary=_glossary(repo_root),
    )
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_fixture(repo_root: Path):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Doubling** \u2014 a test term.\n")
    _write(
        repo_root / "specs" / "product" / "doubling.md",
        "---\n"
        "id: P-DOUBLING\n"
        "title: Doubling\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Doubling\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Numbers can be doubled.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-DOUBLING-001\n"
        "Covers: P-DOUBLING\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a number\n"
        "When it is doubled\n"
        "Then the result is twice the number\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "doubler"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-doubler\n"
        "title: Doubler\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-DOUBLING]\n"
        "---\n"
        "\n"
        "# Doubler\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubler doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling integers.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )
    _write(
        comp / "requirements" / "R-DOUBLER-001.md",
        "# R-DOUBLER-001\n\n**R-DOUBLER-001** \u2014 `double(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "requirements" / "R-DOUBLER-002.md",
        "# R-DOUBLER-002\n\n**R-DOUBLER-002** \u2014 `double(x)` MUST NOT mutate its input.\n",
    )
    _write(
        comp / "acceptance" / "AC-DOUBLER-001.md",
        "# AC-DOUBLER-001\n"
        "\n"
        "Covers: R-DOUBLER-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the doubler requirement text\n"
        "When a reviewer reads it\n"
        "Then it states the doubling rule unambiguously\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-DOUBLER-002.md",
        "# AC-DOUBLER-002\n"
        "\n"
        "Covers: R-DOUBLER-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the doubler input-mutation requirement\n"
        "When a reviewer reads it\n"
        "Then it states the no-mutation rule unambiguously\n"
        "```\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\n```\ndouble(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "gen" / "doubler" / "doubler.py", "def double(x):\n    return 2 * x\n")
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


EXPECTED_IDS = {"AC-DOUBLER-001", "AC-DOUBLER-002"}
RESULTS = {"pass", "fail", "skipped"}


def _judge(bundle):
    return {"result": "pass", "rationale": "The requirement is stated unambiguously."}


def _check_mutation_score(score):
    assert score is None or (
        isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 1
    ), f"mutation_score must be null or a number in [0, 1], got {score!r}"


def test_verify_produces_exactly_one_structured_report(tmp_path):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-doubler", repo_root, judge=_judge)

    # Exactly one report: a single dataclass instance, never a list, tuple or bare dict.
    assert not isinstance(report, (list, tuple, set, dict))
    assert dataclasses.is_dataclass(report) and not isinstance(report, type)

    # Per-criterion results.
    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    ids = [field(c, "id") for c in criteria]
    assert len(ids) == len(set(ids)), f"duplicate criterion entries: {ids}"
    assert set(ids) == EXPECTED_IDS
    for c in criteria:
        assert isinstance(c, dict)
        assert field(c, "result") in RESULTS

    # mutation_score, interface_drift, overall.
    _check_mutation_score(field(report, "mutation_score"))
    assert isinstance(field(report, "interface_drift"), bool)
    assert field(report, "overall") in {"pass", "fail"}

    # JSON form carries the same four parts, as one object.
    d = report.to_dict()
    assert isinstance(d, dict)
    for key in ("criteria", "mutation_score", "interface_drift", "overall"):
        assert key in d, f"to_dict() missing {key!r}"
    assert {c["id"] for c in d["criteria"]} == EXPECTED_IDS
    assert len(d["criteria"]) == len(EXPECTED_IDS)
    for c in d["criteria"]:
        assert c["result"] in RESULTS
    _check_mutation_score(d["mutation_score"])
    assert isinstance(d["interface_drift"], bool)
    assert d["overall"] in {"pass", "fail"}
    assert d["overall"] == field(report, "overall")
    assert d["interface_drift"] == field(report, "interface_drift")
    json.dumps(d)


def test_cli_json_prints_exactly_one_report(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)

    rc = verifier_orchestrator.main(
        ["comp-doubler", f"--repo-root={repo_root}", "--format=json"]
    )
    out = capsys.readouterr().out
    assert rc in (0, 1)

    parsed = json.loads(out)  # raises if more than one JSON document is printed
    assert isinstance(parsed, dict)
    assert parsed.get("component_id") == "comp-doubler"
    for key in ("criteria", "mutation_score", "interface_drift", "overall"):
        assert key in parsed, f"printed report missing {key!r}"
    assert {c["id"] for c in parsed["criteria"]} == EXPECTED_IDS
    assert len(parsed["criteria"]) == len(EXPECTED_IDS)
    for c in parsed["criteria"]:
        assert c["result"] in RESULTS
    _check_mutation_score(parsed["mutation_score"])
    assert isinstance(parsed["interface_drift"], bool)
    assert parsed["overall"] in {"pass", "fail"}
    assert rc == (0 if parsed["overall"] == "pass" else 1)