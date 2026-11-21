# R-KJS-005

**R-KJS-005** — `asset_runner(asset_file)` MUST return a callable
`run(entry: str, args: list)`. Each call copies `asset_file` as it is at
call time to `<tmp>/asset.mjs`, writes `<tmp>/driver.mjs` holding exactly
this driver (196 characters, one line):

    let r,[,,f,e,a]=process.argv;try{let g=(await import(f))[e];r=typeof g=='function'?{v:await g(...JSON.parse(a))}:{e:'no export '+e}}catch(x){r={e:''+(x?.message??x)}}console.log(JSON.stringify(r))

and runs, as `interface/library.md` "Finding node" states:

    node --permission --allow-fs-read=<copy> --allow-fs-read=<driver> <driver> <copy> <entry> <json.dumps(args)>

So the asset may read no other file, write none, and sees no environment
variable but `PATH`. No Python string constant in the module that holds
JavaScript (it matches asset-kinds.md's "Language outside an asset"
pattern and contains `;` or `{`) MAY be 200 characters or longer; the
driver and the `names.mjs` script of `R-KJS-003` are each held in one
constant under 200.
