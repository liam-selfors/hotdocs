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
absent.

**Usable, unreadable, invalid** (`R-LICENSE-010`/`011`). *Unset*: the
variable is unset or empty. *Unreadable*: it is set and the file is
missing or cannot be read. *Invalid*: it is read but is not a JSON
object with an `entries` list; or `corpus_version` is present and not a
non-negative integer; or `block_threshold` is present and not a number
greater than 0 and at most 1 (a JSON `true` or `false` is never a valid
number or integer here); or any entry is not an object with a
`hashes` list of strings and a `risk_tier` of `"high"`, `"medium"`, or
`"low"`. *Usable*: none of those, with at least one entry; a configured corpus
with zero entries is invalid, since a gate that was switched on must
never pass by having nothing to compare.

**Window hashing.** Source text is stripped of `/* */`, `"""`, and
`'''` blocks and of `//` and `#` line comments, then tokenized into
identifiers (`[A-Za-z_][A-Za-z0-9_]*`) and digit runs (`\d+`), each
lowercased. Each run of 9 consecutive tokens, joined by the unit
separator `\x1f`, is hashed as the lowercase SHA-256 hex digest of its
UTF-8 bytes. An entry's score is the share of the component's distinct
window hashes found in that entry's `hashes`; `similarity_score` is
the highest entry score.

**`gate_version`** is `license_scanner@4.0.<corpus_version>+<H>` for a
usable corpus, `<H>` being the first 12 lowercase hex digits of the
SHA-256 of the corpus file's exact bytes. When the scan is not evaluated it is `license_scanner@4.0.0-<reason>`
(`R-LICENSE-005`): `license_scanner@4.0.0-no-reference-corpus`,
`license_scanner@4.0.0-corpus-unreadable`, or
`license_scanner@4.0.0-corpus-invalid`.
