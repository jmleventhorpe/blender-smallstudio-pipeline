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
  - Project folders set per machine in the add-on preferences.
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
    linked publishes that were published again; files built from an older publish are
    flagged.

### Changed

- Tasks have short names: model, rig, layout, light, anim.
