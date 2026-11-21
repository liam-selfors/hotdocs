# R-KPY-007

**R-KPY-007** — `strength_sites(asset_file)` MUST return a
`StrengthSite` for every site of every Python file
(`interface/library.md`), files in order, each file read as UTF-8 and
parsed once with `ast.parse`, its sites in `ast.walk` order of that
tree. A node is a site when it is:

- an `ast.Compare` with exactly one operator, swapped `Eq`↔`NotEq`,
  `Lt`↔`GtE`, `Gt`↔`LtE`, `Is`↔`IsNot`, `In`↔`NotIn`;
- an `ast.BoolOp`, its `And`↔`Or`;
- an `ast.BinOp` whose operator is `Add`↔`Sub`, `Mult`↔`Div` or
  `FloorDiv`↔`Mod`;
- an `ast.Constant` whose value is a `bool`, negated.

Nothing else is a site: a chained comparison, a numeric or string
constant (a docstring included), a unary operator, an augmented
assignment (`+=`), `**`, `@` and the bit operators. `<after>` in the
description is `ast.unparse` of the node with its change applied, which
`strength_sites` then undoes. A directory with no sites gives `[]`.
These are exactly Python's sites in
`specs/architecture/mutation-runs.md` (`D159`, `D172`).
