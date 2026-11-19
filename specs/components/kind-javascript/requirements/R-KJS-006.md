# R-KJS-006

**R-KJS-006** — `run(entry, args)` MUST decode the last non-empty
stdout line of the `R-KJS-005` process as a JSON object:

- with key `v`: return its value as decoded JSON (lists, dicts, `str`,
  `int`/`float`, `bool`, `None`);
- with no `v` and no `e` (the export returned `undefined`): return
  `None`;
- with key `e`: raise `AssetError(<its value>)` — the thrown error's
  `message`, the thrown value as a string when it has none, or
  `no export <entry>` when `entry` is not an exported function.

When the process outlives 30 seconds it is killed and `run` raises
`AssetError("timed out after 30 seconds")`. When `node` is not found,
`AssetError("javascript needs node >= 24")`. When no line decodes to an
object, `AssetError("node exited <code>: <last non-empty stderr line>")`.
Lines the asset itself prints before the last one are ignored.
