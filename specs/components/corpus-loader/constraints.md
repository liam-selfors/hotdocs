# Corpus Loader — Non-Functional Constraints

- **Read-only.** `load_corpus` writes nothing and makes no network or
  model call.
- **Deterministic.** The same files give the same `Corpus`, in the same
  order.
