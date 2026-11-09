# R-ASSEMBLE-014

**R-ASSEMBLE-014** — A line of the target's `interface/library.md` that
  begins `Implements:` names, each in backticks, the documents whose rules
  the component implements: `SPEC_GUIDELINES.md` or a file under
  `specs/architecture/`. `assemble` MUST append each named document's full
  text to `SpecBundle.interface`, and `assemble_criterion` to
  `CriterionBundle.interface`, in the listed order, each after a line
  `## Implements: <path>`. A named path that does not exist raises
  `PreconditionFailure`. A dependency's own `Implements:` line is never
  followed.
