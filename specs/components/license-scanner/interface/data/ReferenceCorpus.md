# `ReferenceCorpus`

The JSON file `VAR-LICENSE-CORPUS-PATH` names (relative paths resolve
against `repo_root`):

```json
{
  "corpus_version": 3,
  "block_threshold": 0.70,
  "entries": [
    {"reference_id": "ref-001", "license_family": "GPL", "risk_tier": "high",
     "hashes": ["<sha256 hex of one 9-token window>", "..."]}
  ]
}
```

`corpus_version` defaults to `0` and `block_threshold` to `0.70` when
absent. A file that is not a JSON object with an `entries` list is
treated as no corpus at all (`R-LICENSE-001`).

**Window hashing.** Source text is stripped of `/* */`, `"""`, and
`'''` blocks and of `//` and `#` line comments, then tokenized into
identifiers (`[A-Za-z_][A-Za-z0-9_]*`) and digit runs (`\d+`), each
lowercased. Each run of 9 consecutive tokens, joined by the unit
separator `\x1f`, is hashed as the lowercase SHA-256 hex digest of its
UTF-8 bytes. An entry's score is the share of the component's distinct
window hashes found in that entry's `hashes`; `similarity_score` is
the highest entry score.

**`gate_version`** is `license_scanner@3.1.<corpus_version>`, with
`corpus_version` `0` when no corpus is reachable (`R-LICENSE-005`).
