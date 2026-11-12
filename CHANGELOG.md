# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Each task's hero shows in the Asset Browser in its own catalog (`character/model`,
  `character/rig`). The `shot_link` setting is gone; an old `pipeline.toml` that sets
  it still loads.
- Sequence and shot nodes carry their task (layout or anim). Add Shot and Omit Shot are
  layout's only.
- Animation is a sequence task, like layout: one file per sequence, playblasts still
  per shot. Dialogs only offer Shot as a category if a project gives shots a task.
- Targets Blender 5.3 (was 5.2 LTS). A strip now follows its shot scene's range by
  itself, so the layout code no longer resets its length.
- Make Editable and Override (was Override for Posing) work on any linked asset in any
  file: a set can be dressed for one shot, or made editable in a shot and published from
  there. Back to Link also throws a made-editable copy away.
- The Loaded panel is gone: the Outliner shows what's loaded.
- Publish follows what was picked last, and is greyed out for a linked asset.

### Added

- Check Updates in an animation file follows layout's latest publish: new, retimed and
  omitted shots, without touching the work in existing ones.
- Animation publishes: each shot's animation node, written for lighting to link, with
  the shot checks and a warning where a shot's cast differs from layout's.
- Animate: in an animation file, gives the selection its own copy of layout's keys, so
  it can be keyed on top of its blocking.
- New Node › Animation builds a sequence's animation file from its layout publish: the
  cut, and a scene per shot linking and overriding layout's shot node (spike T14).
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
- The Pipeline tab in the sidebar of the 3D viewport and the Video Sequencer, with panels
  that show what applies to the open file:
  - Context: the file, what's on show (a shot or the cut) and every warning.
  - Shot: the shot you're in, with frames, cut and cast; Back to Cut, and Follow the cut
    (Sync Scene Time, on in new layout files) so scrubbing the cut shows each shot.
  - Loaded: each asset instance with its ID, the version loaded and whether a newer one
    is out; Select, Update, Override for Posing and Back to Link (new).
  - Publish: the node (the root collection clicked in the Outliner, or holding the
    selection) and the version it becomes, live. A layout file's master scene gets a
    sequence root; it and every shot's root publish the sequence's layout.
    Check shows what Publish would write and runs its checks without writing;
    for a layout, each shot and what changed since the last publish. Replaces the old
    results panel.
  - Workfiles: browse any task's workfiles and when each was saved, and open one.
- Each shot has a root collection named after it, holding its camera and placed assets,
  and a timeline marker; the top-bar label adds the shot or "cut" on show.
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

- Nodes decide everything: a node is a collection carrying what it is (an asset node its
  asset, type and task; a sequence node its sequence; a shot node its shot), and scenes
  and the file's path no longer decide anything but the file's name and Version Up.
  New Node… and the Nodes panel make and edit nodes in the open file, replacing New
  Asset… and New Sequence…. New Workfile saves an empty file in the right place; Save To…
  saves the open file as any task's next workfile. Starter files are gone.
- Publish works on the node and its task. A made-editable copy publishes in its own
  space with no extra workfile; Link Back, a box on the Publish panel, links it back.
  An asset's publish records the instances placed in it. A rig takes its model's latest
  materials from the model's hero; the "built from an older publish" warning is gone.

- Tasks have short names: model, rig, layout, light, anim.
- The code is split by job (project, workfiles, loading, publishing, shots), each with
  core/ for the rules and blender/ for the Blender work and menu actions, plus common/,
  session/ and interface/. Each job registers its own classes.
- Make Editable is only offered in asset workfiles; sequence and shot files get Override
  for Posing instead.
