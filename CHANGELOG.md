# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Spikes T1 to T11 testing the Blender 5.2 behaviour the design depends on, with results.
- Project scaffold: core and Blender layers, extension manifest, tests in plain Python
  and in headless Blender, extension build script and CI.
- Core (M1), all without Blender:
  - Config: built-in `defaults.toml` merged with a project's `pipeline.toml`, checked on
    load with errors that name the file and setting.
  - Path templates that build paths from fields and read fields back out of paths.
  - Naming rules and episode, sequence and shot codes, numbered in steps with room to
    insert.
  - Entity metadata as JSON files, behind a tracker interface (filesystem now).
  - `Project`, `Asset`, `Sequence` and `Shot`, giving every workfile, publish, hero and
    render path, and enforcing which tasks each entity has.
  - File context: what a file is from its path, with the label for the top bar.
- Workfiles (M2):
  - Pipeline menu in the top bar: Open…, New Workfile…, New Asset…, Version Up.
  - Top-bar label saying what the open file is, in the warning colour for publishes,
    unmanaged files and files someone else has open.
  - New workfiles start from a task's starter file (or an empty file), take the project's
    fps and resolution, and asset workfiles get a root collection carrying the asset's
    identity.
  - In-use markers next to open workfiles, with a warning when someone else has a file
    open.
  - Project folders set per machine in the add-on preferences, kept in a settings file
    outside Blender (`~/.config/smallstudio-pipeline/projects.json`, or `%APPDATA%` on
    Windows) so they survive add-on updates and Blender upgrades.
- Asset publishing (M3):
  - Publish checks the asset with publish-validator (bundled, v0.2.0) and the pipeline's
    own checks, then writes a versioned file and the hero file, each with a JSON record.
    The hero is marked for the Asset Browser, links by default, and has a thumbnail and
    a catalog by asset type; kits mark each piece.
  - Blocked publishes list their problems in the 3D viewport sidebar, with Select and Fix.
  - Rigs start from the latest model publish and take its materials on every publish.
  - Assets can be edited (Make Editable) or started inside another asset's file and
    published from there; they're linked back in afterwards.
  - Each project's assets folder becomes an Asset Browser library. Check Updates reloads
    linked publishes that were published again, including ones linked since the file
    opened. Files built from an older publish are flagged, saying what changed and what
    to bring across.
  - The Pipeline menu lists every warning for the open file (a publish, someone else
    has it open, built from an older publish), not just the first.
- Layout and shots (M4):
  - New Sequence… creates a sequence, with the episode's next number and an optional
    title shown beside its code, and opens its layout file: a master scene holding the
    cut. Codes only name sequences; their order will belong to the episode edit (M7).
  - Add Shot adds a shot after the strip at the playhead, numbered between its
    neighbours, with its own scene and camera starting at the project's shot_start
    (101). Omit Shot takes a shot out of the cut and marks it omitted; nothing is
    deleted.
  - Assets placed in a shot get an instance ID on save. Override for Posing overrides
    a linked asset where it stands, keeping its empty as a plain parent.
  - Publishing layout checks each shot (camera, unique instance IDs, known assets),
    publishes the whole file, and writes each shot's frame range, cut points and
    casting into its metadata.
  - The layout playblast renders to the sequence's layout render folder for the
    workfile's version.

### Changed

- Tasks have short names: model, rig, layout, light, anim.
- The code is split by job (project, workfiles, loading, publishing, shots), each with
  core/ for the rules and blender/ for the Blender work and menu actions, plus common/,
  session/ and interface/. Each job registers its own classes.
- Make Editable is only offered in asset workfiles; sequence and shot files get Override
  for Posing instead.
