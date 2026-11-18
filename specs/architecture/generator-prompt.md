---
id: arch-generator-prompt
title: Generator Prompt Layout
status: draft
owners: [pipeline-team]
depends_on: []
---

# Generator Prompt Layout

## Purpose

The exact sections of the prompt `generator`'s `generate` sends, and how
a test builds the component it generates, stated where every criterion's
test author sees them, so that a test checks a section by its heading
rather than by guessing one (`D325`).

## Rules

**Order.** The prompt begins with the fixed instructions: free wording,
holding the line `PROMPT_VERSION: <PROMPT_VERSION>`, the reply-format
markers, and a section `## component_id` whose next line is the
component id. Then come these sections, each a heading line, a newline,
and its content, with one blank line between sections:

| Heading | Content | Present |
| --- | --- | --- |
| `## SPEC` | the bundle's `spec` | always |
| `## INTERFACE` | `interface` | always |
| `## CONSTRAINTS` | `constraints` | always |
| `## DEPENDENCY INTERFACES` | `dependency_interfaces`, as a mapping | always |
| `## DEPENDENCY CONTEXT` | `dependency_context`, as a mapping | always |
| `## VARS` | `vars`, as a mapping | always |
| `## GLOSSARY` | `glossary` | always |
| `## DEPENDENCY USAGE` | one sentence, a blank line, then the non-empty entries of `dependency_usage`, as a mapping | some entry is non-empty |
| `## HINT_CODE` | one sentence, a blank line, then each file, sorted by path, as `--- hint file: <path> ---`, its content, `--- end hint file: <path> ---`, one blank line between files | `hint_code` is not `None` |
| `## RETRY_FEEDBACK` | one sentence, then one line `- <R-id>` per id, in the given order | `retry_feedback` is non-empty |

A mapping is one `### <key>` line followed by that key's value, per key
in sorted order, with one blank line between keys, or `(none)` when it
is empty. No other bundle field, and nothing read from disk, appears.

**Checking a section in a test.** A section's text is everything after
its heading line up to the next line beginning `## `, or the end of the
prompt, without the newlines that end it:

    def section(prompt, heading):
        lines = prompt.split("\n")
        start = lines.index(heading) + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
        return "\n".join(lines[start:end]).rstrip("\n")

**Test fixtures.** A test may pass `generate` any object or mapping with
the `SpecBundle` fields. When a test writes a component under
`repo_root`, its `component.md` sets `sealed: false` and no
`source_path`, overriding the usual sealed default for fixtures: a
sealed component, like one with a pinned `.overrides.json`, is refused
before any model call (`R-GEN-009`), so its mock model is never called.
