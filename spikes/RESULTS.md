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

## T5. Nested libraries in sets: pass (2026-11-02)

- Lib pieces placed in a set (instancing empties) display correctly in layout through two
  levels of linking. Each lib piece is marked as its own asset in the lib hero.
- Republishing the lib (a more detailed rock) and the set (a moved crate) both come
  through, in a link-only layout and in one where the set is overridden for a per-shot tweak.
- Overriding the set in layout and nudging one rock survives reload and both
  republishes, with no broken overrides.

**Finding: overriding an instanced asset loses its placement.** `override_hierarchy_create` from an
instancing empty puts the override at the origin and leaves the empty behind. Baking the
empty's transform into each object works but overrides every object's location, so set
republishes no longer move them. What works: keep the empty as a plain parent (instancing
off), parent the override's top-level objects to it and move `instance_id` to the override
root. Only `parent` is overridden, and locations still follow the set publish.

This applies to any override of an asset dragged in from the Asset Browser, including
characters in layout (settled in M4). It is not the doc's Make Editable (a linked asset
made local inside a set's modeling file), which is untested and belongs to M3.

## T6. Same character in several scenes of one file: pass (2026-11-02)

Three shot scenes each override the same linked character separately. Each keeps its own
keyed pose and its `instance_id` through save, reload and a rig republish, and the new
bone reaches every scene. Blender names the copies `char`, `char.001`, `char.002` (and
`char_rig.001` and so on), so identity has to come from properties, as planned.

## T7. Compositing from EXRs without re-rendering: pass (2026-11-02)

- A comp scene with no objects and no camera renders: only the compositor runs (without a
  camera, a 3D render would fail). 64×36 frames render in well under a second.
- Each shot's comp reads its own multilayer EXR sequence on every frame. Editing the
  shared `seq_comp` group (one stop down) changes every shot's comp output by exactly half.

Blender 5 details for the build code:

- Multilayer EXR output needs `image_settings.media_type = "MULTI_LAYER_IMAGE"` before
  `file_format = "OPEN_EXR_MULTILAYER"`.
- The scene's comp tree is `scene.compositing_node_group`: a `CompositorNodeTree` whose
  Group Output is the result.
- An Image node reading a multilayer EXR shows passes by name (`Combined`, `Alpha`, …),
  not `Image`.
- Node settings such as exposure are input sockets (`inputs["Exposure"]`).

## T8. Preferred Import Method from Python: pass (2026-11-02)

`asset_data.use_preferred_import_method = True` and `preferred_import_method = "LINK"`
set at publish are stored in the hero and readable on linked data; the versioned copy has
no asset data. Options in 5.2: `LINK`, `APPEND`, `APPEND_REUSE`, `PACK`.

Not checked headless: that dragging the hero from the Asset Browser actually links. Check
by hand once in the UI.
