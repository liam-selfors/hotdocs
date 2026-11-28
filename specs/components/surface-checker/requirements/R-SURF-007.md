# R-SURF-007

**R-SURF-007** — For each
  dependency, each name `R-SURF-002` collects that the module has but its documented interface never mentions MUST give
  one `dependency_undocumented` finding,
  `<dep-slug> does not document <name>, which the candidate uses`: the
  documented interface is the text of every `.md` file under
  `<repo_root>/specs/components/<dep-slug>/interface/` (then the tool
  root's, when the repo has none), never the documents their
  `Implements:` lines name: a shared document's names, such as
  `json-values.md`'s `to_json`, are a convention each implementer
  carries itself, not that dependency's offer. A name is mentioned when
  it occurs there as a whole word (`\b<name>\b`). A dependency with no such `.md`
  file, in the repo or the tool root, gets no `dependency_undocumented`
  finding (`D393`).
