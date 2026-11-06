# Architecture

How the add-on's code is laid out, what happens when a file opens and when something is
published, and where to add things. Each module's docstring says more about it.

## Split by job

```
src/smallstudio_pipeline/
├── project/      settings, names and paths, assets, sequences and shots
├── workfiles/    what a file is, new workfiles, Open, Version Up
├── loading/      linking publishes, keeping them current, instances, editable copies
├── publishing/   checks, then writing publishes for other files to link
├── shots/        the sequence layout file and its cut
├── common/       small helpers every job uses
├── session/      what's open, and keeping every job in step as files open and save
└── interface/    the Pipeline menu, the dialogs' choices, what operators share
```

Every job has the same two folders:

- **`core/`** holds the job's rules. It never imports Blender, so it runs, and is tested,
  in plain Python in well under a second.
- **`blender/`** does the job in Blender, and holds the job's menu actions in
  `operators.py`.

`common/` never imports Blender either. A ruff rule (`TID251` in `pyproject.toml`) and a
test stop any `core/` or `common/` file from importing `bpy`, `bmesh` or `mathutils`.

Only operators read `bpy.context`. Everything else takes the scene, collection or
object it works on, so it runs headless in the tests.

## Module map

| Job | `core/` decides | `blender/` does |
| --- | --- | --- |
| **project** | `config` (defaults.toml merged with pipeline.toml), `naming`, `templates`, `metadata`, `tracker`, `project`, `entities`, `machine` (this machine's project list) | `identity` (which asset a root collection is), `preferences` (the project list page) |
| **workfiles** | `context` (what a file is, from its path), `workfiles` (first workfile, next free version), `inuse` (who has a file open) | `workfiles` (start and save), operators: Open, New Workfile, New Asset, Version Up |
| **loading** | `updates` (what's out of date), `casting` (instance IDs) | `libraries` (linking, the Asset Browser library), `updates` (reloading), `instances` (what stands in a shot, Override for Posing), `editable` (Make Editable), operators: Check Updates, Make Editable, Override for Posing |
| **publishing** | `publishing` (targets, plans, records), `catalogs` | `assets` (writing asset publishes, thumbnails), `layout` (Save Copy of a layout file), `in_context` (publishing from a set), `materials` (rig takes model's materials), `validation`, `results` (the sidebar panel), operators: Publish |
| **shots** | `layout` (the cut into each shot's metadata) | `layout` (master scene, strips, playblast path), operators: New Sequence, Add Shot, Omit Shot |

Outside the jobs: `common/` (`errors`, `files`, `reading`), `session/` (`state`,
`handlers`), `interface/` (`menu`, `browse`, `common`), `publishing/checks/` and
`publishing/validation.toml` (the pipeline's own checks and settings), and `wheels/`
(publish-validator, bundled).

## The Pipeline tab

The sidebar of the 3D viewport and the Video Sequencer has a Pipeline tab. Each job draws
its own panel there, in this order: Context (`interface/panels.py`), Shot
(`shots/blender/panels.py`), Loaded (`loading/blender/panels.py`), Publish
(`publishing/blender/panels.py`) and Workfiles (`workfiles/blender/panels.py`).
`interface/panels.both_sidebars()` makes the two classes Blender needs (one per editor)
from one panel class. A panel hides when it doesn't apply to the open file.

Drawing never reads the disk, which may be a slow shared drive: Loaded reads versions
noted on opening, saving and Refresh (`loading/blender/updates.py`); Publish shows what
Check found (`publishing/blender/review.py`); Workfiles lists what was read when its
choices changed. The tests draw each panel into a stand-in layout, since Blender doesn't
draw headless.

## The node

Publishing works on a node: a root collection (`publishing/blender/node.py`). An asset's
root publishes that asset; a layout file's sequence root and every shot's root publish
the sequence's layout. The node is the active collection in the Outliner when it's a
root, else the root holding the selection, else the scene's only one. The Pipeline tab
redraws as the selection, the active collection or the scene on show changes
(`session/handlers.py`: the depsgraph handler and two message-bus subscriptions).

## Registering

Blender calls the package's `register()`. It asks each job to register in turn
(project, workfiles, loading, publishing, shots, interface, session) and the reverse to
unregister. Each job's `blender/__init__.py` registers its own classes, importing them
only when called, so a job's modules can import each other's without loops. `session`
goes last: it adds the load and save handlers and looks at the open file once Blender is
ready.

## When a file opens

1. `session.handlers` refreshes `session.state`: the project (from the file's path, or
   the active project in this machine's settings file), what the file is, and the top
   bar's label.
2. It marks the file as in use, or warns whose it is (workfiles).
3. It adds the project's `assets` folder to Blender's asset libraries, notes the version
   of every publish the file links, and flags any root built from an older publish
   (loading).
4. In a layout file, each workspace's Video Sequencer is pointed at the cut (shots).

Before a save, new instances in shots get their IDs, and a layout file's playblast output
follows the version being saved. After a save, including Version Up, the in-use marker
moves to the new file.

## When an asset is published

```mermaid
flowchart TD
    pick["pick_root: the asset holding the selection"]
    target["publish_target: which asset and task, in context or not"]
    own["Own workfile: rig takes model materials, file saved"]
    ctx["In context: moved into asset space"]
    checks["run_checks: publish-validator"]
    blocked["Blocked: problems listed in the sidebar"]
    workfile["Saved as the asset's next workfile"]
    write["write_publish: hero + versioned file, with records"]
    link["swap_for_link: linked back where it was, file saved"]

    pick --> target
    target --> own --> checks
    target --> ctx --> checks
    checks -- fails --> blocked
    checks -- own workfile --> write
    checks -- in context --> workfile --> write
    write -- in context --> link
```

`write_publish` (`publishing/blender/assets.py`) writes only the root collection and what
it uses, never the artist's whole file. The hero file is overwritten each time and marked
as an asset that links; the versioned file is kept. Each gets a JSON record beside it
(source workfile, Blender version, objects, dependencies, check results), which Check
Updates and the stale warnings read.

In context, writing the asset's workfile happens in a separate headless Blender, because
`bpy.data.libraries.write` crashes on scenes in Blender 5.2.2.

## When a layout is published

1. `shots/blender/layout` makes each shot scene's range what its strip shows, so
   retiming in the cut counts.
2. The file is saved, which numbers any new instances (`crate_03`).
3. Each shot is checked on its own scene: a camera, unique instance IDs (with a Fix),
   and only this project's assets. The sidebar lists problems under each shot's code.
4. The versioned file and hero are Save Copies of the whole workfile
   (`publishing/blender/layout`), since `bpy.data.libraries.write` can't write scenes
   (spike T13).
5. `shots/core/layout.apply_cut` writes each shot's frame range, cut points and casting
   into its metadata, and marks shots with no strip omitted. The record lists the
   publishes the file links.

## Where to add things

- **A task or asset type:** settings only. Add it to `project/defaults.toml` (or a
  project's `pipeline.toml`) with its templates; `config` checks it on load.
- **A publish check:** a class in `publishing/checks/blender/pipeline.py` for every
  project, or in a project's own `checks/` folder for one. Derive it from `AssetCheck` or
  `ShotCheck` there to run it only on assets or only on each shot of a layout publish.
  Switch checks on and off, or make them warnings, in `validation.toml`. Check files
  can't import the add-on, so pipeline facts arrive in the subject's `extras` (see
  `publishing/blender/validation.py`).
- **A menu action:** an operator in its job's `blender/operators.py`, added to that
  file's `CLASSES` and to the menu in `interface/menu.py`. Put the rules in the job's
  `core/`, the Blender work in a module beside the operators, and keep the operator to
  gathering choices and reporting errors.
- **A new job** (animation in M5, say): a folder with `core/` and `blender/`, its
  `blender/__init__.py` registering its classes, and a line in the package's `_jobs()`.
- **A folder layout change:** edit the templates; paths always come from them.

## Tests

`tests/core` runs in plain Python. `tests/blender` runs inside headless Blender
(`tests/blender/run.py`) against temporary projects, with helpers in its `conftest.py`
for making, publishing and linking assets, and its own machine settings file. Spikes in
`spikes/` recorded the Blender behaviour the design relies on;
[RESULTS.md](../spikes/RESULTS.md) says what each found.
