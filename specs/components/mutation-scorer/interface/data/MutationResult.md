# `MutationResult`

```json
{
  "mutation_score": 0.92,
  "mutation_error": null,
  "faulty_tests": [],
  "mutants": 25,
  "killed": 23
}
```

A dataclass with these fields and `to_dict()`. `mutation_score` is
killed over mutants, `1.0` with no mutants, and `null` whenever
`mutation_error` is set or no test was left to run; `faulty_tests` are
the given paths that failed alone in the sandbox
(`specs/architecture/mutation-runs.md`, "Faulty tests"), in the order
given.
