# R-GQE-003

**R-GQE-003** — The `component_docs` view MUST return one row per
  component, its frontmatter fields joined with its full raw text,
  reading under the data contract `SPEC_GUIDELINES.md` §3.4
  (`component.md` is the one file in a component's directory carrying
  frontmatter):

```sql
CREATE OR REPLACE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true) fm
JOIN read_text('{repo_root}/specs/components/*/component.md') t USING (filename);
```

  `{repo_root}` substitution and the `read_text` `filename:=true`
  prohibition are the same as `R-GQE-001`.
