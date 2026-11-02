# Spike results

Blender 5.2.2 LTS (d13f752e3b9c), bundled Python 3.13.13, Linux, local disk.

## T2. Linking a file that contains library overrides: pass (2026-11-02)

Lighting links the animation file's output collection; the character arrives as a linked
override with its action, and the rig and deformed mesh match the animation at every keyed
frame. Republishing the rig with an extra bone comes through on reopening lighting, with
no broken overrides and no resync warnings in the log. Animation publishes can stay live
rigs; no caches needed.

**Finding: custom properties on overrides.** A custom property added to an override that
its reference doesn't have is dropped on save and reload. A property the publish declares
(empty) and marks overridable with
`collection.property_overridable_library_set('["instance_id"]', True)` survives, both in
the animation file and when lighting links it. So every asset publish declares
`instance_id` on its root collection, and each instance fills it in.

## T3. `libraries.write` with overrides: pass (2026-11-02)

- Writing the animation output collection with `path_remap="RELATIVE_ALL"` keeps the
  override, its action and `instance_id`, and links the rig by a relative path. Only the
  character's objects end up local; nothing else from the workfile comes along.
- Lighting linking the written publish behaves exactly as in T2, including the rig
  republish.
- Asset marks: marking the root, writing the hero (temp file in the same folder, then
  `os.replace`) and clearing the mark leaves the workfile unmarked. The hero lists as an
  asset; the versioned copy doesn't. No temp file is left behind.
- Opening a publish directly logs `Library file, loading empty scene`, as the file has no
  scene. Expected; the tool warns when a publish is opened anyway.
