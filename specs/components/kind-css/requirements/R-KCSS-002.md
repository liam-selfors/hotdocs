# R-KCSS-002

**R-KCSS-002** — `layout_errors(asset_file)` MUST return the messages
`specs/architecture/asset-kind-css.md` "Layout" states, in its order:
`["parse error: not UTF-8"]` alone for bytes that are not UTF-8; else
at most one structural message, the first in text order, then one
forbidden message per occurrence in text order. Structural errors:
a `}` with no open block is `unexpected }` at its line; a `{` inside a
rule's block (not an `@media` block) is `unexpected {` at its line; a
`;` outside any block ends a prelude with no block, which is
`at-rule @<name> is not allowed` when it starts with `@<name>` and
otherwise `unexpected ;` at the `;`'s line, an empty one being
skipped; a `;` directly inside an `@media` block is `unexpected ;` too; a block still
open at the end of the file is `unclosed {` at the line of the
outermost open `{`; a declaration (text up to `;` or `}` inside a rule
block) that holds no `:` and is not empty after stripping is
`expected :` at its first non-space character's line; an `@` at the
start of a prelude followed by a name other than `media` (lowercase),
`<name>` being `[A-Za-z0-9_-]*`, is `at-rule @<name> is not allowed` at
the line of the `@`; an `@media` prelude
inside an `@media` block is `@media inside @media` at its line.
