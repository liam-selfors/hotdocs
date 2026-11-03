# Library

```
scan(repo_root: Path) -> SecretScanResult
scan_files(paths: list[Path], repo_root: Path | None = None) -> SecretScanResult
gate_version(repo_root: Path) -> str
propose(repo_root: Path) -> AllowlistProposal
```

`scan` and `scan_files` return a `SecretScanResult` object, never a dict:
a dataclass whose fields are attributes, with a `to_dict()` returning
the JSON shape, `matches` and the other lists holding plain dicts.
`scan` is the full, cache-aware form (`R-SECRET-001`). `scan_files` is
the precommit form (`R-SECRET-008`): no cache lookup, since it runs
before a commit exists to key anything on. `gate_version` returns what
`scan` would put on its result, without scanning (`R-SECRET-010`).
`propose` is the allowlist review aid (`R-SECRET-013`); it raises
`AllowlistInvalidError`, defined in this module, when the current
allowlist is invalid.

## External library

Detection is `detect-secrets`, pinned `==1.5.0` in `requirements.txt`,
with no fallback detector: if it cannot be imported, the call raises
`ImportError`. Exactly these names are used:

- `detect_secrets.SecretsCollection()`, its `scan_file(path_str)`, and
  iteration over it, yielding `(filename, secret)` pairs;
- `detect_secrets.settings.transient_settings(config)`, a context
  manager, with `config` `{"plugins_used": [{"name": <class name>},
  ...], "filters_used": []}`;
- `detect_secrets.core.plugins.util.get_mapping_from_secret_type_to_class()`,
  whose values are the plugin classes (`<class name>` is `__name__`);
- a secret's `type`, `line_number`, and `secret_hash` (the SHA-1 hex
  digest of the secret); its `secret_value` is never read or kept;
- `importlib.metadata.version("detect-secrets")`.

## cache-manager

`scan` loads `cache-manager` from `<repo_root>/gen/cache-manager/` and
uses exactly four of its names: `CacheKey(spec_bundle_hash=...,
gate_inputs_hash=..., gate_version=..., model_pin=...)`;
`get(cache_key, repo_root=...)`; `CachedResult(gate_type="secret_scanner",
payload=<the result's fields as a dict>, stored_at=<a UTC ISO-8601
string from this component's own clock>)`; and `put(cache_key,
cached_result, repo_root=...)` after a fresh scan. A stand-in must
provide all four and no other name is used. A `get` result is a hit only
if its `payload` (read with dual dict-or-attribute access) is non-null.
`cache-manager` being unloadable means no lookup, never a failed scan.

`scan` covers every file under `repo_root`, a test's stand-ins
included, so a stand-in embeds no long random-looking literal — above
all no temporary-directory path; it reads such values from an
environment variable. The compliance
webhook is POSTed with `urllib.request.urlopen` and nothing else, so a
test replaces that function rather than starting a server.
