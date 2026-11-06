import hashlib
import json
import os
import pathlib
import tempfile

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_TEMPLATE = '''
import dataclasses
import json
import os

STORE_PATH = __STORE_PATH__
LOG_PATH = __LOG_PATH__


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    pass


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _load_store():
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_store(store):
    with open(STORE_PATH, "w") as f:
        json.dump(store, f)


def _key_str(cache_key):
    return "|".join([
        str(_field(cache_key, "spec_bundle_hash")),
        str(_field(cache_key, "gate_inputs_hash")),
        str(_field(cache_key, "gate_version")),
        str(_field(cache_key, "model_pin")),
    ])


def _log(event, key_str):
    with open(LOG_PATH, "a") as f:
        f.write(event + ":" + key_str + "\\n")


def get(cache_key, *, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    _log("get", k)
    entry = store.get(k)
    if entry is None:
        return Miss()
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, result, *, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    store[k] = {
        "gate_type": _field(result, "gate_type"),
        "payload": _field(result, "payload"),
        "stored_at": _field(result, "stored_at"),
    }
    _save_store(store)
    _log("put", k)
'''


def test_flagged_sample_preserved_alongside_clean_retry():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = pathlib.Path(tmp)

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        store_path = repo_root / "cache_store.json"
        log_path = repo_root / "cache_invocations.log"

        module_source = _CACHE_MANAGER_TEMPLATE.replace(
            "__STORE_PATH__", repr(str(store_path))
        ).replace(
            "__LOG_PATH__", repr(str(log_path))
        )
        (cache_manager_dir / "cache_manager.py").write_text(module_source)

        flagged_tokens = [
            "alpha", "beta", "gamma", "delta", "epsilon",
            "zeta", "eta", "theta", "iota",
        ]
        clean_tokens = [
            "uno", "dos", "tres", "cuatro", "cinco",
            "seis", "siete", "ocho", "nueve",
        ]
        flagged_window_hash = hashlib.sha256(
            "\x1f".join(flagged_tokens).encode("utf-8")
        ).hexdigest()

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.5,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": [flagged_window_hash],
                }
            ],
        }
        corpus_path = repo_root / "license_corpus.json"
        corpus_path.write_text(json.dumps(corpus))

        gen_dir = repo_root / "gen" / "sample"
        gen_dir.mkdir(parents=True)
        target_file = gen_dir / "sample.py"

        old_env = os.environ.get("VAR_LICENSE_CORPUS_PATH")
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
        try:
            target_file.write_text(" ".join(flagged_tokens) + "\n")
            flagged_result = license_scanner.scan("comp-sample", repo_root)

            target_file.write_text(" ".join(clean_tokens) + "\n")
            clean_result = license_scanner.scan("comp-sample", repo_root)
        finally:
            if old_env is None:
                os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
            else:
                os.environ["VAR_LICENSE_CORPUS_PATH"] = old_env

        assert _get(flagged_result, "evaluated") is True
        assert _get(clean_result, "evaluated") is True
        assert _get(flagged_result, "blocked") is True
        assert _get(clean_result, "blocked") is False
        assert len(_get(flagged_result, "matches")) >= 1

        assert log_path.exists(), "fake cache-manager was never invoked"
        put_keys = []
        for line in log_path.read_text().splitlines():
            if line.startswith("put:"):
                put_keys.append(line[len("put:"):])

        assert len(put_keys) >= 2, "expected two separate cache writes, one per attempt"
        first_put_key = put_keys[0]
        second_put_key = put_keys[1]

        assert first_put_key != second_put_key, (
            "the flagged attempt and the clean retry must not collapse onto "
            "the same cache key, or the retry's write would overwrite the "
            "flagged attempt's record"
        )

        final_store = json.loads(store_path.read_text())

        assert first_put_key in final_store, (
            "the original flagged result is missing from the record"
        )
        assert second_put_key in final_store, (
            "the clean retry result is missing from the record"
        )

        flagged_payload = final_store[first_put_key]["payload"]
        clean_payload = final_store[second_put_key]["payload"]

        assert _get(flagged_payload, "blocked") is True, (
            "the original flagged result was overwritten or erased"
        )
        assert _get(clean_payload, "blocked") is False