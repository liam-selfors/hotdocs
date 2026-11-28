# R-INIT-008

**R-INIT-008** — When `init` creates `.secret-allowlist.json`, it MUST write it as the UTF-8 bytes of `json.dumps({"version": 1, "entries": []}, indent=2)` plus `"\n"`. `init` MUST NOT create any file under `specs/decisions/` other than `R-INIT-001`'s `.gitkeep` (`D199`). When the allowlist exists it is skipped as `R-INIT-001` says.
