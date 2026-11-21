# R-KJS-003

**R-KJS-003** — `surface(asset_file)` MUST return `{"names": names}`,
`names` the sorted list of the module's export names (`default`
included when the module has a default export). It copies the file to
`<tmp>/asset.mjs`, writes `<tmp>/names.mjs` holding exactly

    console.log(JSON.stringify(Object.keys(await import(process.argv[2]))))

and runs `node --permission --allow-fs-read=<copy> --allow-fs-read=<names.mjs> <names.mjs> <copy>`
as `interface/library.md` "Finding node" states, decoding the last
non-empty stdout line as JSON. When `node` is not found, exits non-zero,
times out or prints no decodable list, `names` is `[]`; `surface` never
raises.
