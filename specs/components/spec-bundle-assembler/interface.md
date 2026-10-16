---
id: comp-spec-bundle-assembler-interface
title: Spec Bundle Assembler — Interface
status: draft
owners: [pipeline-team]
---

# Spec Bundle Assembler — Interface

## CLI

```
hotdocs assemble <component-id> [--mode=cold|hint] [--repo-root=<dir>] [--format=json|text]
```

- `<component-id>` — the component's `spec.md` frontmatter `id`.
- `--mode` — `cold` (default; canonical bundle only) or `hint` (adds
  `hint_code`, R-ASSEMBLE-008).
- `--format` — `text` (summary) or `json` (the `SpecBundle` schema below).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Bundle assembled. |
| `1` | Precondition failure — corpus not lint-clean (R-ASSEMBLE-005). |
| `2` | Usage error (unknown component id, bad `--mode`). |

## Library

```
assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle
assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle
```

Both are pure functions over the filesystem state at `repo_root` — no
network access, no model calls, no side effects.

## Data: `SpecBundle`

```json
{
  "component_id": "comp-foo",
  "spec_bundle_hash": "sha256:...",
  "spec": "<spec.md body>",
  "interface": "<interface.md body>",
  "constraints": "<constraints.md body>",
  "dependency_interfaces": { "comp-bar": "<bar/interface.md body>" },
  "vars": { "VAR-FOO-URL": "<the var declaration's body>" },
  "glossary": "<specs/glossary.md body>",
  "hint_code": null
}
```

`hint_code` is `null` in `cold` mode; in `hint` mode it holds the component's
current `gen/<component>/` file contents, keyed by relative path.

## Data: `CriterionBundle`

```json
{
  "component_id": "comp-foo",
  "criterion_id": "AC-FOO-003",
  "covers": "R-FOO-003",
  "criterion_text": "<Given/When/Then prose>",
  "requirement_text": "<the covered R-id's own text from spec.md>",
  "interface": "<interface.md body>",
  "glossary": "<specs/glossary.md body>"
}
```

Narrower than `SpecBundle` by design (R-ASSEMBLE-009) — `test-author`'s
consumer of this schema.
