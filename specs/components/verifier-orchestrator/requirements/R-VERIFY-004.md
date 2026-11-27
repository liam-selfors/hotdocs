# R-VERIFY-004

**R-VERIFY-004** — This component MUST perform the interface drift check:
  every callable `interface/library.md`/`interface/cli.md` documents MUST
  exist in `gen/<component>/` with a matching parameter list; any missing
  callable or parameter mismatch is a hard failure. Public names the
  interface does not document are never drift (`D84`). A callable is
  documented by a line inside a fenced block whose opening fence is
  bare (```` ``` ```` alone, no language): the line starts, in its first
  column, with a name or dotted name followed by `(`, and the parameter
  list is the names up to the matching `)`. A block whose opening fence
  names a language, such as ```` ```python ```` or ```` ```json ````, is
  an example, never documentation (`D387`).
