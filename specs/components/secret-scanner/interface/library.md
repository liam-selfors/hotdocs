# Library

One module file, `secret_scanner.py`, never a package.

```
scan(repo_root: Path) -> SecretScanResult
scan_files(paths: list[Path], repo_root: Path | None = None) -> SecretScanResult
gate_version(repo_root: Path) -> str
propose(repo_root: Path) -> AllowlistProposal
```

`scan` and `scan_files` return a `SecretScanResult` object, never a dict:
a dataclass whose fields are attributes, with a `to_dict()` returning
the JSON shape, `matches` and the other lists holding plain dicts.
`scan` is the cache-aware form (`R-SECRET-001`); `scan_files` the
precommit form, with no cache lookup (`R-SECRET-008`); `gate_version`
returns what `scan` would report, without scanning (`R-SECRET-010`);
`propose` (`R-SECRET-013`) raises `AllowlistInvalidError`, defined in
this module, when the allowlist is invalid. All three read the
allowlist through one shared loader, so the seal and every validity
rule apply identically.

## External library

Detection is `detect-secrets`, pinned `==1.5.0` in `requirements.txt`,
with no fallback detector: if it cannot be imported, the call raises
`ImportError`. Only these names are used:

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

`scan` loads `cache-manager` from `<repo_root>/gen/cache-manager/`, or from the tool root's when absent (`D199`), and
uses exactly four of its names: `CacheKey(spec_bundle_hash=...,
gate_inputs_hash=..., gate_version=..., model_pin=...)`;
`get(cache_key, repo_root=...)`; `CachedResult(gate_type="secret_scanner",
payload=<the result's fields as a dict>, stored_at=<UTC ISO-8601>)`, `stored_at` computed by `scan` itself; and `put(cache_key,
cached_result, repo_root=...)` after a fresh scan. A `get` result is a hit only
if its `payload` (read with dual dict-or-attribute access) is non-null.
`cache-manager` being unloadable means no lookup, never a failed scan.

The compliance webhook is POSTed with `urllib.request.urlopen`
and nothing else, so a test replaces that function.

Implements: `specs/architecture/cli-conventions.md`
