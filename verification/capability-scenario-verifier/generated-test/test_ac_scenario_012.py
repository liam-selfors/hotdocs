import json

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_TEST_AUTHOR_SOURCE = '''
import json
from pathlib import Path

def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    criterion_id = bundle.get("criterion_id") if isinstance(bundle, dict) else getattr(bundle, "criterion_id", None)
    log_path = Path("__LOG_PATH__")
    with open(log_path, "a") as f:
        f.write(json.dumps({"criterion_id": criterion_id}) + "\\n")
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\\n    assert False\\n",
        },
    }
'''


def _setup_repo(repo_root, log_path):
    _write(
        repo_root / "specs" / "product" / "widget.md",
        """---
id: P-X
title: Widget Capability
status: ratified
owners: [alice]
last_ratified_commit: "0000000"
---

# Widget Capability

### CS-X-001

Covers: P-X
Kind: generated-test

```gherkin
Given a widget
When it is used
Then it works
```
""",
    )

    _write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        """---
id: comp-widget
title: Widget
status: ratified
owners: [alice]
last_ratified_commit: "0000000"
realizes: [P-X]
sealed: true
source_path: pipeline/widget/
---

# Widget
""",
    )

    author_source = _TEST_AUTHOR_SOURCE.replace("__LOG_PATH__", str(log_path))
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_source)


def test_recorded_failure_not_hidden_and_not_rerun(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "author_test_calls.log"
    _setup_repo(repo_root, log_path)

    first = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, model="stub-model", seed=0
    )

    first_hit = _get(first, "hit")
    first_report = _get(first, "capability_scenario_report")
    first_capability = _get(first_report, "P-X")
    first_overall = _get(first_capability, "overall")

    assert first_hit is False
    assert first_overall == "fail"

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert record_path.exists()
    record = json.loads(record_path.read_text())
    recorded_report = record["capability_scenario_report"]
    assert recorded_report["P-X"]["overall"] == "fail"

    assert log_path.exists()
    calls_after_first = log_path.read_text().splitlines()
    assert len(calls_after_first) == 1

    check = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    check_hit = _get(check, "hit")
    check_report = _get(check, "capability_scenario_report")
    check_capability = _get(check_report, "P-X")
    check_overall = _get(check_capability, "overall")

    assert check_hit is True
    assert check_overall == "fail"

    second = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, model=None
    )
    second_hit = _get(second, "hit")
    second_report = _get(second, "capability_scenario_report")
    second_capability = _get(second_report, "P-X")
    second_overall = _get(second_capability, "overall")

    assert second_hit is True
    assert second_overall == "fail"

    calls_after_second = log_path.read_text().splitlines()
    assert calls_after_second == calls_after_first