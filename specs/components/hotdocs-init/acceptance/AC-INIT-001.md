# AC-INIT-001

Covers: R-INIT-001
Kind: generated-test

```gherkin
Given an empty directory and a fake tool root
When main(["<dir>", "--yes"]) is called
Then the six directories exist, the four .gitkeep files are empty, specs/glossary.md starts with "# Glossary",
  .secret-allowlist.json parses to {"version":1,"entries":[]}, .gitignore holds
  each of the four lines once, and output_fn received a line exactly equal to "<path>: created" for each of the six directories, the four .gitkeep files, specs/glossary.md, .secret-allowlist.json, and .gitignore

Given main(["<dir>", "--yes"]) is called a second time
When it finishes
Then no file changed, including .hotdocs-tool.json (same bytes and modification time), and each of those lines is now exactly "<path>: skipped (exists)"

Given an existing glossary.md "mine" and an existing .gitignore holding "/.hotdocs/"
When init runs
Then glossary.md is still "mine", and .gitignore gained the other three lines but not a second "/.hotdocs/"
```
