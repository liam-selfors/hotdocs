# R-GEN-002

**R-GEN-002** — Given a `SpecBundle` in `hint` mode, the model call MUST
  additionally include `hint_code` as context, clearly distinguished from
  the cold bundle fields in the prompt — never silently merged in a way
  that makes a later audit unable to tell which parts of the prompt were
  "the spec" versus "the existing code."
