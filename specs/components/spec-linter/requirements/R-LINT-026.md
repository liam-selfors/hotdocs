# R-LINT-026

**R-LINT-026** — Every `D<N>` citation in a live document MUST resolve
  to a real `specs/decisions/D<N>.md` file, **except** `D1`–`D14`,
  frozen historical decisions that live only in `notes/initial-ideas.md`
  by design and MUST NOT be flagged. Closes the one reference kind
  `R-LINT-008`/`009`/`021` already validate for `R-id`/`AC-id`/`P-id`
  but never did for `D<N>`.
