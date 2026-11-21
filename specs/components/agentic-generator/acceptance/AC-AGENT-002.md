# AC-AGENT-002

Covers: R-AGENT-002
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in whose script is: list_files
  with path "bundle", read_file with path "bundle/01-spec.md", read_file
  with path "bundle/02-component-interface.md", write_file with path
  "bundle/x.md", list_files with path "work", then finish
When generate_agentic(bundle for comp-widget-maker, "m",
  repo_root=<tmp>, max_turns=7) is called
Then the recorded results are, in order, "bundle/01-spec.md\nbundle/02-component-interface.md",
  "SPEC TEXT", "IFACE TEXT", an error result starting "path not allowed:",
  "" and "finished"; the loop received seven tools named list_files,
  read_file, write_file, delete_file, check_import, run_scratch_tests and
  finish, max_turns 7, and a system text containing "work/", "scratch/",
  "widget_maker.py" and "finish"; and the prompt names both bundle files

Given also <tmp>/specs/components/widget-maker/component.md whose
  frontmatter has the line "assets: [fake:static/app.txt]"
When generate_agentic is called the same way
Then the system text also contains "static/app.txt"
```
