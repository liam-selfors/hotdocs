# R-GQE-009

**R-GQE-009** — The `bundle_size` view MUST return one row per
  component (`D380`): `component_id` (the bare slug), `generator_words`,
  the words of what its generator reads, and `criterion_words_max`, the
  words of its largest criterion's test-author bundle, `0` with no
  criteria. Words are counted as in `R-GQE-006`; a `component.md`
  drops its `## Rationale`, `## Open questions` and `## Change log`
  sections, and a dependency's `## Purpose` counts with its heading
  word; `\n` is a newline only inside the regular-expression functions; the glossary, `vars` and appended type files are not
  counted:

```sql
CREATE OR REPLACE VIEW bundle_size AS
WITH docs AS (
  SELECT
    regexp_extract(filename, 'specs/components/([^/]+)/', 1) AS c,
    regexp_extract(filename, 'specs/components/[^/]+/(.*)$', 1) AS rel,
    content,
    regexp_replace(content, '^---\n.*?\n---\n', '', 's') AS body
  FROM read_text('{repo_root}/specs/components/*/**/*.md')
),
counted AS (
  SELECT c, rel, content,
    CASE WHEN rel = 'component.md'
      THEN array_to_string(list_filter(regexp_split_to_array(body, '\n## '),
             lambda s: NOT regexp_matches(s, '^(Rationale|Open questions|Change log)\s*\n')), ' ')
      ELSE body END AS text,
    CASE WHEN rel = 'component.md'
      THEN coalesce(list_filter(regexp_split_to_array(body, '\n## '),
             lambda s: regexp_matches(s, '^Purpose\n'))[1], '')
      ELSE '' END AS purpose
  FROM docs
),
w AS (
  SELECT c, rel, content,
    len(list_filter(regexp_split_to_array(trim(text), '\s+'), lambda x: x != '')) AS words,
    len(list_filter(regexp_split_to_array(trim(purpose), '\s+'), lambda x: x != '')) AS purpose_words
  FROM counted
),
own AS (
  SELECT c,
    sum(words) FILTER (WHERE rel = 'component.md' OR rel = 'constraints.md'
      OR starts_with(rel, 'requirements/') OR starts_with(rel, 'interface/')) AS spec_words,
    sum(words) FILTER (WHERE starts_with(rel, 'interface/')) AS interface_words,
    coalesce(sum(words) FILTER (WHERE rel = 'testing.md'), 0) AS testing_words,
    sum(purpose_words) AS purpose_words
  FROM w GROUP BY c
),
arch AS (
  SELECT
    CASE WHEN ends_with(filename, '/SPEC_GUIDELINES.md') THEN 'SPEC_GUIDELINES.md'
      ELSE regexp_extract(filename, '(specs/architecture/[^/]+\.md)$', 1) END AS path,
    len(list_filter(regexp_split_to_array(trim(regexp_replace(content, '^---\n.*?\n---\n', '', 's')), '\s+'),
      lambda x: x != '')) AS words
  FROM read_text(['{repo_root}/specs/architecture/*.md', '{repo_root}/SPEC_GUIDELINES.md'])
),
impl AS (
  SELECT d.c, coalesce(sum(a.words), 0) AS words
  FROM (SELECT c, unnest(regexp_extract_all(
          regexp_extract(content, '(?m)^Implements:(.*)$', 1), '`([^`]+)`', 1)) AS path
        FROM w WHERE rel = 'interface/library.md') d
  JOIN arch a ON a.path = d.path
  GROUP BY d.c
),
deps AS (
  SELECT c, regexp_replace(trim(dep), '^comp-', '') AS dep
  FROM (SELECT c, unnest(string_split(
          regexp_extract(content, '(?m)^depends_on:\s*\[(.*?)\]', 1), ',')) AS dep
        FROM w WHERE rel = 'component.md')
  WHERE trim(dep) != ''
),
dep_words AS (
  SELECT deps.c, sum(o.interface_words) AS interface_words, sum(o.purpose_words) AS purpose_words
  FROM deps JOIN own o ON o.c = deps.dep
  GROUP BY deps.c
),
criteria AS (
  SELECT a.c, a.words + coalesce(r.words, 0) AS words
  FROM (SELECT c, words, regexp_extract(content, '(?m)^Covers:\s*(\S+)', 1) AS covers
        FROM w WHERE starts_with(rel, 'acceptance/')) a
  LEFT JOIN w r ON r.c = a.c AND r.rel = 'requirements/' || a.covers || '.md'
)
SELECT
  o.c AS component_id,
  o.spec_words + coalesce(i.words, 0) + coalesce(dw.interface_words, 0)
    + coalesce(dw.purpose_words, 0) AS generator_words,
  CASE WHEN max(cr.words) IS NULL THEN 0
    ELSE max(cr.words) + coalesce(o.interface_words, 0) + coalesce(i.words, 0)
      + coalesce(dw.interface_words, 0) + o.testing_words END AS criterion_words_max
FROM own o
LEFT JOIN impl i ON i.c = o.c
LEFT JOIN dep_words dw ON dw.c = o.c
LEFT JOIN criteria cr ON cr.c = o.c
WHERE o.spec_words IS NOT NULL
GROUP BY o.c, o.spec_words, o.interface_words, o.testing_words, i.words, dw.interface_words, dw.purpose_words;
```
