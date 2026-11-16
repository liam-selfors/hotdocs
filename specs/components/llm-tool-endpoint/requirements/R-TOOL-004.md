# R-TOOL-004

**R-TOOL-004** — A tool call MUST give `execute` the tool's name and an
  argument dict. An `execute` that raises gives the error result
  `tool error: <exception class name>: <message>`. A call naming no tool
  in `tools`, or whose arguments are not a JSON object, is never passed
  to `execute` and gives the error result `unknown tool: <name>` or
  `arguments must be a JSON object`. Every error result goes back to the
  model like any other result, and the loop continues.
