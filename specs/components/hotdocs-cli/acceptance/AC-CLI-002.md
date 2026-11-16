# AC-CLI-002

Covers: R-CLI-002
Kind: generated-test

```gherkin
Given a project with a fake "lint" and a working directory set to it
When main(["lint","a.md"]) is called with no --repo-root
Then the fake received ["a.md","--repo-root=<project, absolute>"]

Given main(["lint","--repo-root", "<project>", "a.md"]) and
  main(["lint","--repo-root=<project>"])
When called
Then the fake received exactly the given tokens after "lint", with no second --repo-root

Given a project holding hotdocs.toml, a fake "lint" that records os.environ.get("VAR_HOTDOCS_CONFIG"),
  and a working directory elsewhere
When main(["lint","--repo-root","<project>"]) is called, with the variable unset, then set to "/x"
Then the fake saw "<project>/hotdocs.toml", then "/x", and afterwards the variable is back to unset
```
