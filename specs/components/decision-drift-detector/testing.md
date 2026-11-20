# Testing decision-drift-detector

**Decision fixtures.** A test writes each decision record as
`specs/decisions/D<N>.md` with frontmatter exactly as `SPEC_GUIDELINES.md`
§2 defines it, `---` in column 0 of line 1:

```
---
id: D2
title: Second decision
status: draft
owners: [pipeline-team]
supersedes: D1
builds_on: [D1]
---

# D2
```

`supersedes` is one bare id (`supersedes: D1`), never a list: a list
such as `supersedes: [D1]` is not read as a supersedes edge.
`builds_on` is a list of bare ids. Omit either key when it does not
apply.

**Git fixtures.** A test that needs commit history runs `git init` in
its temporary `repo_root`, passing `-c user.name=t -c user.email=t@t
-c commit.gpgsign=false` to every git call, and commits each state
with `git add -A` then `git commit -q -m <message>`.
