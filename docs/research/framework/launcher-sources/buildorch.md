# Build orchestration, determinism, deltas, load order and save safety for the launcher

Research by Claude (subagent "buildorch"), 2026-10-19. Scope: the launcher that runs the long FO4-to-Starfield
conversion on a player's Windows PC, must give byte-identical FormIDs on every PC, resumes after crashes, and later
installs third-party mods on top of the converted core in a stable order.

## How to read this

- **verified**: I read the source myself. The URL is given. Where the page could not be fetched, I read the
  same text in the project's own Git repository through GitHub code search. That URL is given as a `github.com` path
  plus the quoted fragment.
- **supported hypothesis**: follows from verified facts or from the repo's own evidence, but nobody has tested it
  for our case.
- **unresolved**: unknown, or I could not read the source.
- **repo**: a fact read from this repository at the current checkout. File paths are relative to the repo root.

**Pages I could not read.** The WebFetch proxy kept rate-limiting me (HTTP 429), so no claim below rests on these
pages: daemonology.net/bsdiff, docs.python.org (cmdline page), numpy.org (the random compatibility page; part of it
read through GitHub instead), the reproducible-builds.org sub-pages (only the docs index was read), the CPython
zlib-ng commit page, issues.guix.gnu.org/51536 (OpenBLAS), and taleoftwowastelands.com/faq.

---

## 0. What the repo already has (the baseline we are judging against)

- **repo:** `docs/ai/launcher-backbone.md` and `src/fo4sf/launcher/`: a JSON recipe driver (steps with argv, inputs,
  outputs, deps, timeout, retries, code paths). State goes to `state.json`, written atomically. A step is reused only
  if it finished with exit 0, its outputs exist, its fingerprint (argv, cwd, input identities, code content) is
  unchanged, and none of its dependencies ran this run. It has a lock file, a `--min-free-gb` floor, `--idle`, and a
  build manifest. The `same-ids` check has verdicts IDENTICAL / SAME_IDS / IDS_DIFFER / INCOMPLETE.
  `mods.py` has a draft mod manifest (id, version, core range, Starfield pin, plugins, requires, load_after) and a
  deterministic resolver.
- **repo:** `docs/RESUMING-BUILDS.md`: per-model checkpoints with SHA-256 checks on every output, and input identity
  that includes converter source hashes, Python/numpy/Pillow versions and the texconv hash. Archive identity is path,
  size and mtime (not content).
- **repo, verified on one PC:** the same inputs re-staged gave a byte-identical `FO4TerrainCore.esm` and
  `_Mars.esm`, and every formids.json section was identical (launcher-backbone.md, "First PC run" step 2). No
  cross-machine run yet (plan task L4).
- **repo:** `driver.code_hash()` hashes all of `src/fo4sf` when a step declares no `code` paths
  (`src/fo4sf/launcher/driver.py`, `code_paths`). So any converter edit invalidates every such step. Directory
  inputs are fingerprinted by file count, total bytes and newest mtime (`path_identity`), not by content.
- **repo:** `--idle` passes `IDLE_PRIORITY_CLASS` (0x40) as `creationflags` to each step's child process
  (`driver.py` lines 44, 195 to 202).
- **repo:** C# FormID reservations are a persisted `{stable key: id}` map, ids 0x800 to 0xFFFFFF, written sorted by
  id (`dotnet/PluginSpike/StableFormIds.cs`). Python builds allocate append-only by class, so earlier ids never
  move (`scripts/terrain/make_core64c.py`, comments near lines 1591 and 2051).
- **repo:** the .NET projects target `net9.0` (`dotnet/*/*.csproj`). `src/fo4sf/btd.py` calls `zlib.compress`.
  texconv is called for BC1/BC4/BC5 (`src/fo4sf/pipeline.py` lines 232 to 236).

---

## 1. Build orchestration on a consumer PC

### 1.1 What the known tools do (and what to borrow)

| Tool | Mechanism (what I read) | Label | Borrow? |
|---|---|---|---|
| Bazel remote cache | Two stores: "The action cache, which is a map of action hashes to action result metadata" and "A content-addressable store (CAS) of output files." [github.com/bazelbuild/bazel docs/remote/caching.mdx]. In the Remote Execution API, an `Action` holds "The digest of the Command" and `input_root_digest` [github.com/bazelbuild/remote-apis build/bazel/remote/execution/v2/remote_execution.proto] | verified | **Yes, the idea.** Key = hash(command + every input's content digest + tool digest). Value = output digests. Outputs are stored by content. We already do this for each model checkpoint. Lift it to each step. |
| ccache | Has a "direct mode" (default true) that records the headers the compiler used, with a documented catch about headers that were *not* used but would have been [github.com/ccache/ccache doc/manual.adoc] | verified | **The lesson:** a cache keyed on the inputs you *observed* misses inputs that appear later. For us: a new DLC or a new loose file in Data must change the key even if no step "read" it last time. |
| DVC run-cache | "Every subsequent time a stage runs under the same conditions, the previous results can be restored instantly", on by default [github.com/treeverse/dvc.org content/docs/user-guide/pipelines/run-cache.md] | verified | **Yes.** Keep old results by key, not only the last one. A player switching between converter versions or toggles gets old outputs back from the cache instead of rebuilding. The cost is disk, and the PC rule keeps 40 GB free. |
| Snakemake | `RerunTrigger` enum: `MTIME`, `PARAMS`, `INPUT`, ... [github.com/snakemake/snakemake src/snakemake/settings/enums.py]. Its message suggests `--rerun-triggers mtime` to fall back to the old behaviour [src/snakemake/workflow.py] | verified (enum, partial) | **The idea:** name the reasons a step reruns (code / params / input / env / mtime) and report the reason to the user ("rerunning meshes: converter mesh.py changed"). |
| doit | "Tracks file dependencies and targets (MD5 or timestamp). Skips tasks that are already up-to-date." [github.com/pydoit/doit doc/index.rst] | verified | Nothing beyond what we have. Our driver already does this with SHA-256. |
| Luigi | A task is done when `complete()` returns True. By default that means "all the targets defined as outputs" exist. "Luigi verifies that you adhere to the contract" [github.com/spotify/luigi doc/tasks.rst] | verified | **Avoid** output-exists as the only completion test. A half-written file "exists". We already need exit 0 + hash + `build-state.json` complete; keep that. |
| Prefect | Cache policies `INPUTS`, `TASK_SOURCE` ("only considers raw lines of code in the task (and not the source code of nested tasks)"), and combinable as `INPUTS + TASK_SOURCE` [github.com/PrefectHQ/prefect docs/v3/concepts/caching.mdx, docs/v3/advanced/caching.mdx] | verified | **A warning:** a key that hashes only the task's own source misses changes in the helpers it calls. Our `code_hash` is the opposite extreme: it hashes the whole package. Both are wrong. See 1.2. |
| Nix | Not read in this session. | unresolved | The idea that matters (outputs addressed by hash of all inputs, including the toolchain) is the same as Bazel's. |

**Supported hypothesis: keep our own small JSON-recipe driver and do not adopt one of these tools.** None of them
ships to a player's Windows PC without a runtime the player must install: Bazel needs Java, Snakemake needs Python
plus its own deps, DVC needs Python plus Git. And the steps are already our own scripts with their own checkpoints.
What to borrow is three ideas, not code:
1. Action key = content hash of (argv, every input's content digest, tool digests, *the code the step actually
   imports*).
2. A content-addressed output store that keeps more than the last result (DVC run-cache).
3. A named rerun reason (Snakemake triggers).

### 1.2 Rebuild only what a converter change touches

- **repo:** today, a step without `code` paths hashes all of `src/fo4sf`, so touching `textures.py` reruns the
  terrain step. A step *with* `code` paths hashes only those files, so a change in a helper it imports is missed:
  the Prefect TASK_SOURCE problem.
- **Supported hypothesis, recommended:** compute each step's code set from its import closure. Run the step's entry
  script under `python -I -X importtime`, or walk the imports statically with `modulefinder`/`ast`, once per
  converter version. Store the closure in the recipe lock, and hash the closure's file contents. For C# steps, hash
  the built assembly and every DLL it loads (Mutagen version included), not the .cs files.
- **Supported hypothesis:** add an explicit **converter output version** per step (an integer the step's owner bumps
  when output bytes are meant to change). Two keys then do two jobs: the code hash says "could have changed", the
  version says "should have changed". When the code hash changes, the version does not, and the output differs,
  that is a determinism or refactor bug to report. That gives a free regression test on every player's PC.
- **Supported hypothesis:** per-model checkpoints (RESUMING-BUILDS.md) are already the fine-grained layer. The step
  layer should stay coarse. Do not try to make the driver know about 50,000 NIFs.

### 1.3 Parallelism vs memory on 16 to 32 GB machines

- **repo, verified on the PC:** one terrain archive build had a peak working set of 2,049 MiB (commit 2,788 MiB)
  (`docs/ai/research-log.md` around line 916). One staged core is 4.45 GiB listed and 0.3 to 1 GiB unique
  (launcher-backbone.md).
- **verified:** Windows job objects can cap "the job-wide sum of their committed memory. When a process attempts to
  commit memory that would exceed the job-wide limit, it fails." (`JOB_OBJECT_LIMIT_JOB_MEMORY` 0x200)
  [github.com/MicrosoftDocs/sdk-api sdk-api-src/content/winnt/ns-winnt-jobobject_basic_limit_information.md]
- **Supported hypothesis, recommended:** schedule by a **memory budget**, not a fixed worker count. Each step (or
  each worker kind) declares `peak_commit_mb`, measured and stored in the recipe. The driver runs N workers while
  the sum of their declared peaks is at most (physical RAM minus 6 GB for Windows and the user) times 0.7, and never
  more than physical cores minus 1. Put all children in one job object with a job memory limit, so a misdeclared
  step fails cleanly instead of paging the PC to death. A step that fails with an out-of-memory error is retried
  alone (N = 1) before it counts as failed.
- **unresolved:** the real per-worker peaks for meshes, textures and navmesh at full Commonwealth scale. Only the
  terrain number above is measured.
- **Supported hypothesis:** parallelism must never change output bytes. Every parallel stage writes per-item outputs
  and is merged in sorted key order; no shared counter allocates FormIDs. See 2.

### 1.4 Keeping the machine usable

- **verified:** "The *_PRIORITY_CLASS values affect the CPU scheduling priority of the process. For processes that
  perform background work such as file I/O ... it is not sufficient to adjust the CPU scheduling priority; even an
  idle CPU priority process can easily interfere with system responsiveness when it uses the disk and memory.
  Processes that perform background work should use the PROCESS_MODE_BACKGROUND_BEGIN ..." And
  PROCESS_MODE_BACKGROUND_BEGIN "can be specified only if hProcess is a handle to the current process."
  [github.com/MicrosoftDocs/sdk-api sdk-api-src/content/processthreadsapi/nf-processthreadsapi-setpriorityclass.md]
- **verified:** a child created without priority flags gets NORMAL "unless the priority class of the creating process
  is IDLE_PRIORITY_CLASS or BELOW_NORMAL_PRIORITY_CLASS. In this case, the child process receives the default
  priority class of the calling process." [same repo, nf-processthreadsapi-createprocessw.md]
- **Consequence (supported hypothesis):** today's `--idle` (the flag on each child) lowers CPU priority only. Disk
  and memory priority stay normal. And because background mode can only be set by a process on itself, the
  launcher cannot impose it from outside. Each step's entry point (Python and the dotnet tools) must call
  `SetPriorityClass(GetCurrentProcess(), PROCESS_MODE_BACKGROUND_BEGIN)` itself when an env var says so
  (e.g. `FO4SF_BACKGROUND=1`). Grandchildren (texconv, Archive2) inherit IDLE CPU priority per the rule above. Their
  I/O priority is unresolved.
- **Supported hypothesis:** add a **"pause while Starfield or Fallout 4 runs"** rule (the repo already reserves the
  GPU for game tests). Pause between steps, or suspend the job, rather than relying on priority alone.

---

## 2. Reproducibility: same bytes on every PC

### 2.1 How others prove it

- **verified:** reproducible-builds.org lists the variance topics it treats separately: timestamps, SOURCE_DATE_EPOCH,
  timezones, locales, archive metadata, stable order for inputs and for outputs, randomness, build path, value
  initialization, version information, "Recording the build environment", and checksums
  [https://reproducible-builds.org/docs/]. I could not read the sub-pages (see the list at the top).
- **verified:** diffoscope "will try to get to the bottom of what makes files or directories different. It will
  recursively unpack archives of many kinds and transform various binary formats into more human readable form"
  [github.com/anthraxx/diffoscope README.rst]. **Supported hypothesis:** it knows nothing of ESM/BA2/NIF. Our
  `same-ids` raw record walk is the domain-specific equivalent, and the right one to keep. diffoscope is still
  useful one level down: a BA2 extracted to a folder, or a DDS.
- **Supported hypothesis, the practice to copy:** a *rebuilder* setup, where independent machines build the same
  recipe and publish the hashes. For us that means every player's launcher can (opt-in) report a **build
  fingerprint** after a build: one hash per output plugin and archive, plus the build manifest's pin set. A
  public table of "manifest pins → output hashes" then proves determinism across many CPUs for free, and spots the
  odd PC whose outputs differ.

### 2.2 Sources of non-determinism, ranked for this pipeline

| # | Source | Evidence | Label | What to do |
|---|---|---|---|---|
| 1 | **Different inputs that look the same**: game version, missing DLC, loose files or a CC plugin in Data | repo: `detect` refuses unknown hashes and missing DLC; the PC lacks 4 DLC | verified (repo) | FormIDs depend on the input set. Treat "DLC set" as part of the core's identity (see Q3). |
| 2 | **Python hash randomization**: iteration order of `set` and `frozenset` of str/bytes changes per process | "hash randomization is enabled by default"; `PYTHONHASHSEED` "allows you to set a fixed value for the hash seed secret" [github.com/python/cpython Doc/using/cmdline.rst] | verified | Never iterate a set to allocate ids or write records. Sort first. CI test: run the build twice with `PYTHONHASHSEED=0` and `=1` and compare bytes. Setting the seed in the launcher hides bugs, so use it only as the test lever. |
| 3 | **zlib implementation**: CPython 3.14 on Windows switched to zlib-ng | "On Windows, zlib-ng is now used as the implementation of the zlib module in the default binaries. There are no known incompatibilities between zlib-ng and the previously-used zlib implementation." [github.com/python/cpython Doc/whatsnew/3.14.rst]. 3.16 adds `zlib.zlib_version_info` and `ZLIBNG_VERSION_INFO` [Doc/whatsnew/3.16.rst] | verified (the switch); **supported hypothesis** that compressed *bytes* differ (the statement is about compatibility, not identical output) | `btd.py` uses `zlib.compress`, and records in plugins may be zlib-compressed. Pin the Python minor version in the manifest. Better: ship the interpreter (embedded Python) with the launcher. Record `zlib.ZLIB_RUNTIME_VERSION` (and zlib-ng's version where present) in the manifest. Test that 3.13 and 3.14 give the same bytes. |
| 4 | **Floating point across CPUs**: numpy SIMD dispatch picks code paths at runtime by CPU | numpy scans CPU features at runtime; `NPY_DISABLE_CPU_FEATURES` "will exclude simd features at runtime" [github.com/numpy/numpy doc/source/reference/global_state.rst; doc/source/reference/simd/build-options.rst]. "Even on the same platform, a different build of numpy may use a different version of this matrix decomposition algorithm from the LAPACK that it links to" [doc/source/reference/random/compatibility.rst] | verified (dispatch exists; LAPACK builds differ); **supported hypothesis** that our float maths gives different last bits on AVX-512 vs AVX2 CPUs | Anything whose float result feeds a FormID decision, a sort key, a cell assignment or a written float should be computed in float64 and then quantized (rounded to the file's precision, e.g. `np.float32`) before comparison or writing. `navmesh.py` already rounds through `np.float32`. Add a CI job with `NPY_DISABLE_CPU_FEATURES` set to a low tier, compare bytes against the default run. Avoid BLAS/LAPACK calls (`linalg`, `@` on large matrices) in byte-producing paths. |
| 5 | **x87 vs SSE** | x64 Windows builds use SSE2 for doubles | supported hypothesis | Not a risk for 64-bit Python and .NET. Only matters if a 32-bit tool is in the chain. |
| 6 | **texconv / DirectXTex** | "texconv utility uses DirectCompute compression by default for BC6H/BC7, -nogpu disables use of DirectCompute" [github.com/microsoft/DirectXTex CHANGELOG.md] | verified | We use BC1/BC4/BC5 today (CPU codecs). If BC7 is ever used, pass `-nogpu`, or results depend on the GPU. Pin and hash the texconv binary: today it ships "with xEdit", so its version varies by player. Whether the CPU BC codecs give identical bytes across CPU instruction sets is **unresolved**. Test it. |
| 7 | **.NET culture-sensitive string operations** | On .NET 5+ on recent Windows, globalization uses ICU, and the doc's example gives different results than .NET Core 3.1 (`3` vs `0, 0, 3`) [github.com/dotnet/docs docs/core/extensions/globalization-icu.md]. .NET Core 3.0 changed float parsing and formatting for IEEE 754-2008 compliance [docs/core/whats-new/dotnet-core-3-0.md] | verified | Every `OrderBy(string)`, `string.Compare` and `ToString()` or `Parse` of a float in a byte-producing path must use `StringComparer.Ordinal` / `CultureInfo.InvariantCulture`. **repo:** `dotnet/SliceDoor/Inspect.cs:92` and `Check.cs:61` order by a key with the default comparer. If the key is a string, the order follows the culture. These are inspection outputs (low risk), but a guard rule should catch the pattern everywhere. `dotnet/ActorRaider/Program.cs:82` uses `float.Parse` without invariant culture: on a German-locale PC, "1.5" will not parse as 1.5 (supported hypothesis). Run the build in a CI job with `LANG`/culture set to de-DE. |
| 8 | **Timestamps** in outputs (TES4 header, BA2, logs folded into outputs) | not checked | unresolved | `same-ids` level 2 already compares TES4 headers. Add a check that two builds a minute apart are byte-identical (the PC run did this: IDENTICAL). |
| 9 | **Directory listing order** | NTFS returns names sorted. Other file systems and other tools may not | supported hypothesis | **repo:** `driver.code_hash` sorts. `os.walk` in `path_identity` only sums, so order does not matter there. Grep shows unsorted `os.walk`/`listdir` in `launcher/files.py`, `detect.py`, `manifest.py` and `meshcheck.py`. Fine for reports, but a guard rule should require `sorted()` wherever the order reaches output bytes. |
| 10 | **Path separators and case** | **repo:** `checkpoints.staged_path` resolves case-insensitively and refuses ambiguity; `code_hash` normalizes to `/` | verified (repo) | Keep. Hash keys must use the in-archive path form (lowercase, backslash or slash, chosen once), never the host path. |
| 11 | **Threading** | | supported hypothesis | Allowed only when each thread's output is independent and merged in sorted order. No thread may take "the next FormID". |
| 12 | **Archive2 (BA2 writer)** | **repo:** the dry run was byte-identical on one PC | unresolved cross-PC | Archive2 is Bethesda's tool, from the player's own Creation Kit install, and its version varies. Hash `Archive2.exe` into the manifest. Long term, a BA2 writer we own removes the variable. |

### 2.3 The FormID-specific rule

**Supported hypothesis, the strongest available guarantee:** byte-identical *files* on every PC is the goal.
Identical *FormIDs* is the contract. Make the FormID map an **input** rather than an output: ship
`formids.lock.json` (stable source key, e.g. FO4 plugin + FO4 FormID + record class, mapped to Starfield
FormID) with each core release, the same pattern as `StableFormIds.cs`. A build on a player's PC then *reads* ids
from the lock and only allocates (append-only) for keys the lock lacks. It fails, or marks the build "not
release-identical", if it had to allocate any. Then even an unnoticed ordering bug cannot move an existing id. It
can only cause a refusal. The lock holds no game content: only ids and keys. The keys are FO4 FormIDs and editor IDs
(see the legal note in 3.2, unresolved).

---

## 3. Deltas instead of rebuilding

### 3.1 Tools

| Tool | What I read | Label |
|---|---|---|
| xdelta3 | Apache 2.0 on main / 3.2.x (the original GPL version is separate). "a C library and command-line tool for delta compression using VCDIFF/RFC 3284 streams" [https://github.com/jmacd/xdelta]. `-B` "Source window/cache size. Default: 64 MiB". "The source window size (set by -B) used by the decoder must be greater than or equal to the source window size used by the encoder" [github.com/jmacd/xdelta site/docs/commandline.md, site/docs/non-seekable-source.md]. "The source window size is limited to 2GB unless XD3_USE_LARGESIZET is defined to 1" [xdelta3/xdelta3.h] | verified |
| Octodiff | rsync-style signature, then delta, then patch. 2048-byte chunks, Adler32 rolling plus SHA1. Signature about 1.3% of the basis; delta creation needs about 5x the signature size in memory [https://github.com/OctopusDeploy/Octodiff]. Apache 2.0 [LICENSE.txt in that repo] | verified |
| bsdiff | Page not readable (rate limit). | unresolved (commonly said to need memory several times the file size; not checked) |
| Wabbajack | Uses Octodiff (`Wabbajack.Compiler/PatchCache/OctoDiff.cs`, patch cache file named `{srcHash}_{destHash}.octodiff`) and xxHash64 (`Wabbajack.Installer/Utilities/BinaryPatching.cs`). GPL-3 (`LICENSE.txt`) [github.com/wabbajack-tools/wabbajack]. Its docs: "Wabbajack cannot inline modified files, so instead we just include the difference between the original and modified version", "original + patch = final", "we only include patch in the .wabbajack file which, by itself, is just gibberish", "we copy instructions on how to modify the copyrighted material" [https://wiki.wabbajack.org/modlist_author_documentation/Pre-Compilation.html] | verified |

**Supported hypothesis:** deltas fit our case badly for most outputs:
- Our outputs are *new* files (Starfield plugins, NIFs, DDS), not modified FO4 files. A delta needs a "source" the
  player has. The only source is the FO4 file, and an FO4 NIF and a Starfield NIF share few bytes. The patch would
  be roughly the output's size and would carry converted (derived) content.
- A delta saves CPU (hours) at the price of a download (GBs) and a hosting bill. It also gives up the "built from
  your own files" story.
- Deltas *are* useful between **two of our own builds** (core v1 → v2 on the player's PC). There the source is our
  previous output, which the player already has. Octodiff's signature approach suits that: tiny signature, then
  delta. But a rebuild with the run-cache (1.1) already gives most of it for free.

### 3.2 The legal angle

- **verified:** Wabbajack's stated position is that it ships instructions and patches that are "gibberish" alone,
  and its rules forbid uploading certain generated outputs (VRAMR, ParallaxGen) to Nexus or its CDN
  [Pre-Compilation page above]. That is the community's practice, not a legal ruling.
- **unresolved:** whether a binary delta from a Bethesda file to a converted file is a derivative work under US/EU
  law, and what Bethesda's or Microsoft's EULA and mod terms say about converting one game's assets into another.
  I found no primary legal source in this session. Tale of Two Wastelands (FO3 data into FNV, built from the
  player's own copy) is the closest precedent, but its FAQ was rate-limited. **Hand this to the "precedents" agent.**
- **Supported hypothesis, recommended default:** ship nothing derived from game bytes (no patches of game files, no
  converted assets). Ship code, recipes, the FormID lock (ids + FO4 keys) and hashes, and build on the player's PC.
  Revisit only with a written legal opinion.

---

## 4. Load order for mods built on the core

### 4.1 LOOT

- **verified:** LOOT is GPL-3.0. It lists Starfield first among supported games [https://github.com/loot/loot]. The
  Starfield masterlist is CC0-1.0, at branch v0.29 [https://github.com/loot/starfield].
- **verified:** masterlist and userlist top-level keys: `prelude`, `bash_tags`, `globals`, `groups`, `plugins`
  [https://loot-api.readthedocs.io/en/latest/metadata/file_structure.html]. Plugin keys: `name` (exact or regex),
  `group` (default `default`), `after` ("must load after, but which are not dependencies"), `req` ("This plugin will
  load after any plugins listed"), `inc`, `msg`, `tag`, `url`, `dirty`, `clean`
  [https://loot-api.readthedocs.io/en/latest/metadata/data_structures/plugin.html]. A group has `name`
  (case-sensitive), `description` and `after`. Sorting fails on an undefined group or a cycle
  [.../data_structures/group.html].
- **verified, sorting:** "Morrowind and Starfield plugins need all their masters installed, or sorting fails". There
  are three graphs (non-masters, blueprint masters for Starfield only, non-blueprint masters), and metadata linking
  plugins in different graphs is silently ignored. Edge order: masters, req, after, hardcoded, groups, overlaps,
  then tie-breaks by the **existing load order**. The final order is masters, non-masters, blueprint masters
  [https://loot-api.readthedocs.io/en/latest/api/sorting.html]. "blueprint master plugins always load after all
  other plugins" [github.com/loot/libloot docs/api/sorting.rst]. LOOT keeps the current relative order where the
  graph allows [https://loot.readthedocs.io/en/stable/app/sorting.html].
- **verified:** libloot added "Support for Starfield's new medium plugin type (via esplugin and libloadorder)", and
  writes implicitly-active BlueprintShips plugins into plugins.txt
  [github.com/loot/libloot docs/api/changelog.rst].
- **Consequence (supported hypothesis):** LOOT's output **depends on the player's current load order** (the
  tie-break). So LOOT alone does not give "the same order on every PC". Our resolver must fix the core-plus-mods
  order itself (deterministic topological sort, ties broken by id, as `mods.py` does). LOOT is then a *checker* or
  a source of extra metadata. Or: publish a LOOT group (e.g. `FO4SF Core`, `FO4SF Mods` after it) to the CC0
  Starfield masterlist so players using LOOT get a compatible order.

### 4.2 Mod Organizer 2

- **verified:** `meta.ini` keys MO2 reads and writes include `modid`, `version`, `newestVersion`, `ignoredVersion`,
  `installationFile`, `repository` (default `Nexus`), `gameName`, `url`, `hasCustomURL`, `nexusFileStatus`,
  `category`, `comments`, `notes`, `author`, `uploader`, `converted`, `validated`, `color`, `endorsed`, `tracked`,
  `installedFiles` (modid, fileid), and a `Plugins` group
  [https://raw.githubusercontent.com/ModOrganizer2/modorganizer/master/src/modinforegular.cpp]. It has **no**
  dependency, version-range or load-after field.
- **verified:** MO2 has Starfield support in `modorganizer-game_bethesda` (`src/games/starfield/`). Its save reader
  reads `Plugins`, `LightPlugins`, and `MediumPlugins` when `saveVersion >= 122`, with a v122 core list
  (`Starfield.esm`, `Constellation.esm`, `OldMars.esm`, `BlueprintShips-Starfield.esm`, `SFBGS003/006/007/008.esm`)
  [github.com/ModOrganizer2/modorganizer-game_bethesda src/games/starfield/starfieldsavegame.cpp, starfieldsavegame.h].
  It warns about INI settings that stop the game reading plugins.txt [gamestarfield.cpp].

### 4.3 Vortex

- **verified:** Vortex's mod rule types are `'before' | 'after' | 'requires' | 'conflicts' | 'recommends' |
  'provides'` [github.com/Nexus-Mods/modmeta-db src/types.ts, docu.md]. Vortex sorts plugins with built-in LOOT, plus
  user rules and groups. Cyclic rules stop the sort [https://github.com/Nexus-Mods/Vortex/wiki/MODDINGWIKI-Users-FAQ].

### 4.4 Thunderstore, CurseForge, Modrinth

- **verified:** Thunderstore `manifest.json` has `name` (a-z A-Z 0-9 _, max 128), `description` (at most 250
  characters), `version_number` (Major.Minor.Patch), `website_url` (required key, may be empty) and
  `dependencies` as exact strings `"{team}-{package}-{version}"`, e.g. `"MythicManiac-TestMod-1.1.0"`. It always
  shows the highest version [https://wiki.thunderstore.io/mods/creating-a-package]. Dependencies are **exact
  versions, not ranges.**
- **verified:** a CurseForge modpack manifest lists `files[]` as `projectID` + `fileID` + `required`, has an
  `overrides` folder, and carries **no hashes**. The same page notes Modrinth carries `hashes` (sha1, sha512)
  [https://gdlauncher.com/docs/modpack-manifest-format].

### 4.5 Version ranges

- **verified:** semver: 0.y.z is initial development, where anything may change. Major must go up on a
  backward-incompatible change. Build metadata is ignored for precedence [https://semver.org/].
- **verified:** node-semver: `^1.2.3` := `>=1.2.3 <2.0.0-0`; `^0.2.3` := `>=0.2.3 <0.3.0-0`; `^0.0.x` allows no
  updates; pre-releases are excluded from ranges unless a comparator with the same tuple has one
  [https://github.com/npm/node-semver].
- **Supported hypothesis, recommended:** give the core **two versions**:
  - a *content* semver, where the major goes up when any FormID is removed or changes record type (an
    incompatible change for mods and saves), the minor when FormIDs are only added, and the patch when record
    bodies change with no id change;
  - a *build fingerprint* (hash of the output plugins) in the build metadata `+fp.<hash>`, which semver ignores.

  Mods declare a caret range on the content version (`^1.4`). The launcher checks both: the range for
  compatibility, and the fingerprint for "is this the release build or a local variant". The `same-ids` verdicts
  already map onto this: IDENTICAL = same fingerprint, SAME_IDS = patch, IDS_DIFFER = minor if ids were only added,
  major otherwise. The v6c → v6e change (one FormID went DOOR → STAT) is a *major* change under this rule.

### 4.6 What our mod manifest must carry (recommended v1)

| Field | Why | Borrowed from |
|---|---|---|
| `id` (reverse-DNS or `author.name`, a-z0-9._-) | stable key; ties broken by id | Thunderstore name, our mods.py |
| `version` (semver) | ordering, updates | all |
| `core` (semver range on the core's content version) | compatibility | npm-style |
| `core_build` (optional exact fingerprint) | for mods that patch exact record bytes | our same-ids |
| `starfield` (optional exact game version or range) | an engine update breaks plugins | mods.py |
| `plugins[]` with name, sha256 and type (full / medium / small) | the type decides the slot limits and the save's plugin lists | MO2 save reader, libloot |
| `archives[]` with name and sha256 | | Modrinth hashes |
| `requires[]` (id + range) | hard deps | Vortex `requires`, LOOT `req` |
| `load_after[]` (id) | soft order, no dep | LOOT `after`, Vortex `after` |
| `incompatible[]` (id + range) | refuse early | LOOT `inc`, Vortex `conflicts` |
| `save_policy` (`safe_add`, `safe_update`, `new_game_required_from`) | see 5 | SS2 FAQ practice |
| `source` (URL) and `source_sha256` of the download | provenance, Wabbajack-style matching | Wabbajack `.meta`, Modrinth |
| `loot_group` (optional) | export to LOOT userlist | LOOT groups |

---

## 5. Save compatibility across builds

### 5.1 How a save points at plugins and forms

- **verified (Skyrim, UESP):** the save stores a plugin list (`pluginCount` plus names; SE adds `lightPluginInfo`),
  a `formIDArray`, and 3-byte RefIDs whose top 2 bits give the type (0 = index into formIDArray, 1 = Skyrim.esm
  default form, 2 = created, 0xFF plugin). changeForms carry a RefID, `changeFlags`, a record **type** byte, a
  version, and data that may be zlib-compressed [https://en.uesp.net/wiki/Skyrim_Mod:Save_File_Format].
- **verified (Starfield, community tooling):** the save header lists plugins. MO2 reads three lists (full, light,
  medium; medium from save version 122) (4.2). Nexus's StarfieldSaveTool documents `pluginInfoSize`, `pluginInfo`,
  `lightPluginCount` and `lightPlugins`, and notes that from saveVersion 140 a byte says whether extra info is
  present [github.com/Nexus-Mods/StarfieldSaveTool README.md, SFS-decompressed.bt]. A third-party RE project
  reports the `.sfs` as a `BCPS` container of zlib chunks, a body starting `SFS_SAVEGAME`, a plugin list, and an
  "FO4/SSE-shaped file-location table" with a formID array, and says "the ChangeForms encoding is undocumented"
  [github.com/pjmagee/starfield-complete-planet-survey-mod re/FINDINGS.md]. That project's claims are labelled
  `save-verified` by its author but are **unreviewed by us**: treat them as supported hypothesis.
- **Supported hypothesis (from the structure above):** a save refers to our core's forms by **plugin name plus the
  form's local id**, and stores the record **type** of each changed form. So:
  - renaming a core plugin orphans everything;
  - a FormID that disappears leaves a change form pointing at nothing;
  - **a FormID whose record type changes** (DOOR → STAT, as in v6c → v6e) leaves a change form of the old type on
    a form of the new type. That is the worst case, and the reason `same-ids` already calls it IDS_DIFFER;
  - ids that are only added are safe for the save itself (scripts aside).

### 5.2 What breaks, beyond ids

- **verified (Papyrus, Skyrim CK wiki):** saves store running function stacks and variable/property values. A
  script removed from an object "will still exist on the object when the save is loaded". A property removed
  becomes inaccessible and is dropped at the next save. A property whose type changes has its saved value
  discarded. "Masterfile value changed: The saved value is not overwritten". A form referenced by a script variable
  whose plugin is gone becomes a placeholder with ID #0 [https://ck.uesp.net/wiki/Save_File_Notes_(Papyrus)].
  **Supported hypothesis:** Starfield's Papyrus behaves the same (same engine family). Unverified.
- **Consequence:** a core update that changes a VMAD default (e.g. the door `DestinationX/Y/Z` properties) does
  **not** reach an existing save for references whose script has already run. "Save-compatible" must be judged per
  change, not per FormID set.
- **verified (community practice):** SS2's FAQ: "Generally speaking, you should never delete a mod from an active
  save" and "The only mods that are generally 'safe' to uninstall are mods that don't have an ESP"
  [https://wiki.simsettlements2.com/getting-started/faq]. A Starfield mod author: removing plug-ins "can leave one
  with a corrupt save game", and safe removal points are only before a new game or at Unity
  [https://www.nexusmods.com/starfield/articles/687]. A Step admin, from memory, on load order changes and the
  renumbering of FormIDs in a save, explicitly hedged as "subject to being incorrect"
  [https://stepmodifications.org/forum/topic/15366-adding-mods-mid-playthrough/]. Nexus noted early on that
  Starfield seems to treat light and full plugins as separate load orders, and that a master losing its light flag
  corrupts it [https://www.nexusmods.com/news/14888].
- **Supported hypothesis:** big mods do not *prove* save compatibility. They promise it by policy (no record
  removal, no type changes, scripts only add properties, a new-game warning in the changelog when they break it).
  I found no tool that checks it. Our `same-ids` is already stronger than community practice.

### 5.3 What the launcher should check before replacing a core under an existing save (recommended)

1. **Read the save header** (plugin lists only; the format is documented by MO2 and StarfieldSaveTool) and refuse
   if the save names a plugin the new install will not have, or the plugin's type (full/medium/small) changes.
2. **Compare the old core's and new core's FormID tables** (`same-ids` level 2):
   - IDENTICAL or SAME_IDS (record bodies only): allow, and list the changed records;
   - ids only added: allow;
   - **any id removed or any type change: block by default.** Offer "keep the old core for this save" (the
     content-addressed store makes that cheap) or "start a new game".
3. **Script-property diff** (VMAD) for records whose script or properties changed: warn that existing references
   keep their saved values.
4. **Plugin order:** the new order's position of every plugin the save names must be the same, or the save must
   tolerate it. **unresolved** for Starfield; test it.
5. **Always back up the save first** and record which core fingerprint each save was last made with (a small
   `saves.json` the launcher owns, never inside the save).
6. Per-save core pinning: a player can keep one save on core 1.x while starting a new game on 2.x. That needs
   side-by-side cores and a profile switch, which `restore` already approximates.

---

## Questions this raises for our launcher

Each question has: **why it matters**, **what would answer it**, and a **recommended default** where the evidence
supports one.

### A. Determinism and FormIDs

**Q1. Do two different PCs (different CPUs, ideally Intel AVX-512 vs AMD AVX2) produce byte-identical core plugins
and archives from the same inputs and the same pinned toolchain?**
- Why: this is the project's contract. One PC proved IDENTICAL; cross-machine is plan task L4.
- Answer by: the same recipe on a second machine, or the same PC with `NPY_DISABLE_CPU_FEATURES` set to a low tier
  plus a second checkout path. Then `same-ids` and hash every output.
- Default: the release is defined as "IDENTICAL on at least two dissimilar CPUs". Until then, label builds
  "single-machine verified".

**Q2. Should FormIDs come from a shipped lock file (`formids.lock.json`) instead of being re-derived by allocation
order on each PC?**
- Why: a lock turns any hidden ordering bug into a refusal instead of a silent id shift that breaks saves and mods.
- Answer by: (a) is the lock content free of game data (ids plus FO4 keys only)? Legal check, Q13. (b) Measure its
  size for the full Commonwealth.
- Default: **yes**. Read ids from the lock, allocate only for missing keys, and mark such a build
  "not release-identical".

**Q3. Is the DLC set part of the core's identity, or must the core be identical with and without the DLC?**
- Why: the owner's PC lacks 4 DLC. If DLC records take part in allocation order, base-game FormIDs shift with the
  DLC set.
- Answer by: build the base-game-only recipe and an all-DLC recipe, then compare the base-game section of
  formids.json.
- Default: allocate base-game ids in a range that never depends on DLC, and DLC content in a separate plugin or id
  range per DLC. Then "core" means the same thing on every PC.

**Q4. Which Python, numpy, .NET, Mutagen, texconv and Archive2 versions are pinned, and do we ship them?**
- Why: zlib-ng on Windows from Python 3.14 (verified), numpy SIMD dispatch (verified), texconv from the player's
  xEdit, and Archive2 from the player's CK are all variables.
- Answer by: build once with Python 3.13 and once with 3.14 and diff. Then two texconv versions.
- Default: ship an embedded Python plus a wheels lock, a self-contained .NET publish, and a texconv we pin by hash.
  Archive2 is required, but its hash is recorded and checked against a known table, like `known_sources.json`.

**Q5. Does any byte-producing path depend on set iteration, culture, unsorted directory listings or float bits
before quantization?**
- Why: these are the classic sources (2.2). `ActorRaider` uses `float.Parse` without invariant culture.
- Answer by: CI runs the same build under `PYTHONHASHSEED=0` and `=1`, a de-DE culture and `NPY_DISABLE_CPU_FEATURES`,
  and compares bytes. Add guard rules: no `OrderBy`/`Compare` on strings without `Ordinal`; no `float.Parse` or
  `ToString` without invariant culture; `sorted()` around listdir/walk wherever the result reaches outputs.
- Default: add these four CI variations as the determinism suite. Cost: one extra synthetic build each.

**Q6. Are texconv's CPU BC1/BC4/BC5 codecs bit-identical across CPUs and thread counts?**
- Why: textures are most of the bytes. If they vary, archive hashes vary even when plugins do not.
- Answer by: compress the same 20 test images on two CPUs, with and without `-singleproc` (texconv has an
  `OPT_FORCE_SINGLEPROC` option), and compare.
- Default: until answered, compare texture *content* (decoded pixels within a tolerance) separately from plugin
  bytes, and never let texture bytes into a FormID decision.

### B. Orchestration

**Q7. What should a step's cache key contain, and how do we find the code a step depends on?**
- Why: today it is all of `src/fo4sf` (too coarse) or listed files (too fine, the Prefect TASK_SOURCE problem).
- Answer by: prototype an import-closure hash for one step and compare how often it invalidates vs today on the
  last 50 commits (`git log`).
- Default: key = sha256(argv, cwd-relative paths, input content digests (or size+mtime for the immutable FO4
  archives, as now), import closure file hashes, tool binary hashes, step `output_version`).

**Q8. Do we keep more than one cached result per step (a DVC-style run-cache)?**
- Why: switching converter versions or toggles back and forth should not cost hours. But the PC keeps 40 GB free.
- Answer by: measured unique bytes per step output (the `measure` command). Most staged data is hard links.
- Default: keep the last 2 results per step, with LRU eviction under a user-set cap (default 20 GB). Never evict
  the result a current save is pinned to.

**Q9. How many workers per stage on 16 GB vs 32 GB?**
- Why: one archive step peaked at about 2 GiB commit. Unknown for meshes, textures and navmesh at full scale.
- Answer by: record `peak_commit_mb` per step on the owner's PC (job object accounting) during the first full run.
- Default: the memory-budget scheduler from 1.3, with a job memory limit and an automatic retry at N = 1 on an
  out-of-memory error.

**Q10. How do we keep the PC usable: CPU only, or I/O and memory priority too?**
- Why: IDLE CPU priority does not lower disk and memory priority (verified). Background mode can only be set by a
  process on itself (verified).
- Answer by: a 10-minute test with a game or browser open, with today's `--idle` vs self-set
  `PROCESS_MODE_BACKGROUND_BEGIN` in each step's entry point. Measure the interactive app's frame times or
  input lag.
- Default: each step's entry point sets background mode when `FO4SF_BACKGROUND=1`. The driver pauses between steps
  while Starfield.exe or Fallout4.exe runs.

**Q11. What does "resume" promise after a power cut mid-write?**
- Why: atomic state and per-model checkpoints exist. A torn output file must never be reused.
- Answer by: a fault-injection test (kill the step at random points, power-cut simulated with
  `FlushFileBuffers` skipped) on synthetic fixtures.
- Default: write every output as temp file + fsync + rename (StableFormIds.cs already does). A step is complete
  only after its outputs are hashed into state.json.

### C. Deltas and legal

**Q12. Do we ever ship deltas?**
- Why: deltas save hours of CPU but need hosting and carry derived content.
- Answer by: the legal question (Q13), plus measured delta sizes core v(n) → v(n+1) with Octodiff and xdelta3
  (`-B` at least the file size).
- Default: **no deltas of game-derived files.** Deltas between two of the player's own local builds are allowed if
  they ever beat the run-cache, which is unlikely.

**Q13. Is a FormID lock, or any delta derived from Bethesda files, distributable?**
- Why: decides Q2 and Q12.
- Answer by: the "precedents" agent (TTW, Skyblivion, Wabbajack policies) and, before release, a written opinion.
- Default: ship only code, recipes, hashes and the id lock. Hold the id lock back until it is cleared.

### D. Load order and mod manifests

**Q14. Who decides the final load order: our resolver, LOOT, or the player's mod manager?**
- Why: LOOT's tie-break uses the player's current order (verified), so it is not the same on every PC. MO2 and
  Vortex sort through LOOT plus user rules.
- Answer by: test that LOOT, given our core and two sample mods, produces our resolver's order, with and without a
  CC0 masterlist group entry.
- Default: our resolver writes plugins.txt for the core and our mods. We publish LOOT groups (`FO4SF Core` →
  `FO4SF Mods`) to the CC0 Starfield masterlist so LOOT users agree. We never move plugins we do not own.

**Q15. Which plugin type is the core (full, medium, small), and can mods be medium/small?**
- Why: the type decides id ranges and which save list a plugin appears in (MO2 reads three lists). A type change
  later corrupts saves (Nexus warning). The core has 683,870 records (repo), which is very likely more than a medium plugin's id space
  (supported hypothesis; the medium id limit was not read in this session).
- Answer by: the plugin-format research (sfstack agent). Then a test save with a medium mod.
- Default: the core is a full master, fixed forever. Mods may be medium if they fit. The manifest states the type,
  and the launcher refuses a type change under a save.

**Q16. Is our manifest v1 (4.6) enough, and do we accept ranges (npm style) or exact versions (Thunderstore
style)?**
- Why: exact pins break every mod on each core patch. Ranges need the core's semver to mean something.
- Answer by: write the core version policy (content semver from `same-ids` verdicts) and check it against the
  v6c → v6e history.
- Default: caret ranges on the core's content version, plus an optional exact `core_build` for byte-level patch
  mods. Every downloaded file carries a sha256.

### E. Saves

**Q17. What exactly happens in Starfield when a core FormID changes record type, or disappears, under an existing
save?**
- Why: it is the worst case. v6c → v6e did it (010027A0 DOOR → STAT).
- Answer by: an in-game test. Make a save near Red Rocket with v6c, load it under v6e, read the log and check the
  door reference. Then remove one REFR and repeat.
- Default (until tested): block both cases under an existing save.

**Q18. Does Starfield remap a save's plugin indices by name when the load order changes, or does order matter?**
- Why: decides whether mods may be inserted before or after the core in a running game.
- Answer by: an in-game test with two test plugins swapped, plus a read of the save's plugin list before and after.
- Default (until tested): never reorder plugins a save names. Append new mods only.

**Q19. Do Starfield Papyrus saves keep old script property values the way Skyrim's do?**
- Why: our door VMAD changes (`DestinationX/Y/Z`, `UseDestinationPosition`) would not reach references whose
  scripts already ran.
- Answer by: an in-game test. Save with an old door VMAD, update the core, load, and log the property values.
- Default (until tested): treat a VMAD property change as "new game recommended" for the affected cell, and say so
  in the update notes.

**Q20. What should the launcher store about saves?**
- Why: to say "this save was made with core 1.4.2+fp.ab12" before an update.
- Answer by: the save header reader (plugin lists, documented by MO2 and StarfieldSaveTool) plus our own
  `saves.json`, keyed by save file hash.
- Default: back up before every core change. Record the core fingerprint per save. Offer per-save core pinning,
  with old cores kept in the content-addressed store.
