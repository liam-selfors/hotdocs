# R-GQE-006

**R-GQE-006** — The `component_size` view MUST return one row per
  component, the word count of every doc under a component's directory:

```sql
CREATE OR REPLACE VIEW component_size AS
SELECT
  regexp_extract(filename, 'specs/components/([^/]+)/', 1) AS component_id,
  sum(len(list_filter(
    regexp_split_to_array(
      trim(regexp_replace(content, '^---\n.*?\n---\n', '', 's')),
      '\s+'
    ),
    lambda x: x != ''
  ))) AS word_count
FROM read_text('{repo_root}/specs/components/*/**/*.md')
WHERE NOT ends_with(filename, '/testing.md')
GROUP BY 1;
```

  `{repo_root}` substitution is the same as `R-GQE-001`. `trim()`
  without an explicit character set strips spaces only, not newlines —
  the `list_filter` MUST remain, to drop the spurious trailing empty
  token every file's own trailing newline otherwise produces (`D13`).
  The frontmatter-stripping `regexp_replace` MUST keep its `'s'` flag,
  for the same DOTALL reason as `R-GQE-004`.
  A component's `testing.md` is test-only text the generator never sees
  and is not counted (`D341`).
