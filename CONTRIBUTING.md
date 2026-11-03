# Contributing

## Setup

See the Development section of the [README](README.md). Before pushing, run the same
checks as CI:

```bash
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest
```

```bash
blender -b --factory-startup --python tests/blender/run.py
```

## Code style

Written to be read and extended by other TDs.

- **Layers.** `core/` never imports Blender (`bpy`, `bmesh`, `mathutils`); a test and a
  ruff rule enforce it. Anything touching Blender goes in `blender/`.
- **Structure.** Light OOP: entity classes with methods (`shot.workfile_path(task, version)`),
  plain records for data. No deep hierarchies or frameworks.
- **Context.** Only operators read `bpy.context`. Helpers take the scene, collection or
  object they work on as arguments, so they run headless.
- **Errors.** Core raises `PipelineError` subclasses with plain-English messages that
  say what to do. Operators catch them and show them with `self.report()`. Use `logging`
  for the console.
- **Types.** Type hints on function signatures; pyright runs in basic mode.
- **Comments.** A one-line docstring on public functions. Comment only where Blender
  behaves in a non-obvious way, and say why.
- **Formatting.** `ruff format`, line length 100.
- **Names.** Tasks have short names (`model`, `rig`, `layout`, `light`, `anim`). Other
  names use American spelling (`color`), matching Blender's API.

## Commits

Small, focused commits with a short imperative subject ("Add version helpers"). Update
`CHANGELOG.md` under Unreleased for anything user-facing.
