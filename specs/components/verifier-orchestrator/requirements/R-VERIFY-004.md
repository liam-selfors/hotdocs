# R-VERIFY-004

**R-VERIFY-004** — This component MUST perform the interface drift check:
  every callable `interface/library.md`/`interface/cli.md` documents MUST
  exist in `gen/<component>/` with a matching parameter list; any missing
  callable or parameter mismatch is a hard failure. Public names the
  interface does not document are never drift (`D84`).
