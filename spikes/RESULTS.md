# Spike results

Blender 5.2.2 LTS (d13f752e3b9c), bundled Python 3.13.13, Linux, local disk.

## T1. Overwriting a linked hero file: local pass, NAS run still to do (2026-11-02)

`local` mode, one Linux machine, local disk: a second Blender holds the shot open while
the hero is overwritten (temp file in the same folder, then `os.replace`, retried on
`PermissionError`). The overwrite succeeds first time, `library.reload()` in the watcher
shows v002, and reopening the shot shows v002.

Still to run by hand: project on the NAS, the watcher on Windows (then Linux) with the
shot open in the UI, the publish from the other machine.

## T4. Sequence lighting file load time: pass (2026-11-02)

Ryzen 9 3900X (24 threads), 30 GB, local NVMe, warm disk cache. Each shot scene links its
own animation publish (3 overridden characters, every bone keyed), a shared 200k-vertex
set and a local light rig. Times are file open in a fresh Blender, minus Blender's own
startup.

| Rig | Shots | Open | Memory after open | Peak (3 scenes evaluated, 1 frame rendered) |
| --- | --- | --- | --- | --- |
| 200 bones, 40k verts | 10 | 0.12 s | 419 MB | 723 MB |
| 200 bones, 40k verts | 20 | 0.22 s | 486 MB | 758 MB |
| 200 bones, 40k verts | 40 | 0.47 s | 621 MB | 844 MB |
| 200 bones, 40k verts | 40, after rig republish | 0.49 s | 618 MB | 839 MB |
| 400 bones, 150k verts | 10 | 0.22 s | 502 MB | 1301 MB |
| 400 bones, 150k verts | 20 | 0.50 s | 627 MB | 1292 MB |
| 400 bones, 150k verts | 40 | 0.95 s | 870 MB | 1617 MB |
| 400 bones, 150k verts | 40, after rig republish | 0.71 s | 868 MB | 1675 MB |

- Checked: after the republish every one of the 120 overrides has the new bone count, so
  the resync really ran on open; it costs little.
- First evaluation of a shot scene is a fraction of a second (0.2 s including reading back
  a deformed 150k-vertex mesh).
- One file per sequence is fine at these sizes, with a wide margin under the 60 s threshold.

Limits: generated rigs have no drivers, shape keys or extra meshes, and the files are on
local NVMe. Rerun with `--out` on the NAS, and with a real character once one exists.

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

Checked by hand in the UI (2026-11-02): with the publish folder registered as an asset
library, dragging the hero from the Asset Browser into a shot links it (relative library
path, rig and mesh from the library, nothing appended), placed by a local empty that
instances the linked collection. No preference change needed.

## T9. Per-shot property overrides on linked data: pass, kept as fallback only (2026-11-02)

Superseded by the native approach in T11; kept in case a tweak can't be expressed that way.

Python can set properties on linked data in memory (object visibility, motion blur,
modifier settings, material node values, pose-bone properties); none of it is saved, so it
has to be re-applied on every open. Settings were a sequence-level JSON file plus a text
datablock per shot (shot wins), applied by a text module on `load_post` and `render_pre`.

- Each shot rendered in its own fresh Blender (as a farm would) shows its settings: red
  from the sequence file, green from a shot's material setting, black where a shot hides
  the body.
- Rendering all three shots in one session, green first, leaves nothing behind: the
  applier resets everything any shot touches before applying the next shot's settings.
- With auto-run scripts blocked, nothing applies and the shots render untouched.

**Finding: shared datablocks.** In a sequence lighting file, a character's material comes
from the rig library and is shared by every shot. Per-shot material settings therefore
have to be re-applied for whichever shot is rendering or active, not once on load.
Objects are per shot (each shot's animation publish has its own), so object settings are
looked up within the shot's scene.

**For the build:** the tool ships the applier in the add-on, not as a text module, so
farm workers need the add-on installed (or auto-run scripts allowed). Switching the active
scene in the UI also needs to re-apply; not testable headless.

## T10. Asset previews when publishing: pass (2026-11-02)

`collection.asset_generate_preview()` works headless: the hero's asset gets a 128×128
preview of the asset, stored in the hero file and readable when linked. The fallback
(render an image, load it with `ed.lib_id_load_custom_preview` under
`temp_override(id=...)`) also works, for a nicer framed thumbnail later.

## T11. Per-shot shader controls without scripts: pass (2026-11-02)

The character's material reads its tint through an Attribute node of type View Layer,
which looks the name up on the view layer, then the scene, then the world. The lighting
file sets plain custom properties, saved like any local data, so nothing is re-applied:

- a world shared by every shot scene holds sequence-level values (shot 0010: red);
- a scene property overrides it for one shot (0020: green);
- a view layer property overrides that for one render layer (0030: blue).

All three render correctly in Cycles and EEVEE, with auto-run scripts blocked, one shot
per fresh Blender and all shots in one session. The material stays shared and linked.

**For the build:** assets expose their lighting controls as View Layer attributes, named
consistently (e.g. `char_tint`). Lighting sets defaults on the sequence world and per-shot
values on scenes. Visibility and holdouts use per-view-layer collection settings; anything
else goes back to animation or the asset.

## T12. Publishing an asset from inside another asset's file: pass (2026-11-03)

Tested as Blender tests in `tests/blender/test_in_context.py` rather than a spike script,
since it exercises the real Make Editable and Publish.

- Make Editable appends the asset's latest versioned publish as a plain local copy where
  the linked one was: the placing empty's transform is baked into the copy's objects and
  kept on its root collection, and the empty is removed. (A first version kept the empty
  as the copy's parent; in the UI that read as an object and a collection tangled
  together.) It appends from the versioned file because Blender won't append cleanly from
  the hero this file already links ("ID is already linked"), which gave .001 names.
- Publishing the copy first moves it into the asset's own space with the inverse of the
  stored placement, objects added in place included. A crate placed at (5, 0, 0) and
  turned 90°, with a lid added at (5, 1, 2) in the set, publishes with the lid at (1, 0, 2).
- The copy is saved as the asset's next workfile, published, and swapped back for a link
  where it was; the copy's meshes and materials are removed too, so editing again doesn't
  give .001 names. The set file is saved. An asset started from scratch in the set is
  linked where it was built.
- Linking back must reload the asset's library first: the version made editable is still
  loaded, and linking again hands that back, so the set kept showing the old crate.
- Publish leaves Edit Mode first: edits made in Edit Mode only reach the mesh then.

**Finding: `bpy.data.libraries.write` can't write scenes.** Writing any scene, even an
empty one, crashes Blender 5.2.2. Collections are fine. The asset's workfile is therefore
built by a short headless Blender that appends the written root into a fresh scene.

## T13. A layout publish as a Save Copy of the workfile: pass (2026-11-03)

A sequence layout file (a master scene cutting two shot scenes, each with a camera, the
set linked through an empty and the character overridden under its placing empty) is
published with `wm.save_as_mainfile(copy=True, relative_remap=True)`, to the versioned
file and to the hero through a temp file and a rename.

- Both copies open with every scene, the cut's strips pointing at their shot scenes, the
  set linked and placed, and each shot's character with its own pose, its placement
  under the empty and its `instance_id`. No missing data or broken overrides.
- Library paths are relative and resolve from the publish folder.
- The session stays on the workfile, and the workfile on disk is untouched.
- Save handlers run for a copy too (`save_pre` and `save_post`, twice per copy), with
  `bpy.data.filepath` still the workfile's. So anything the pipeline does on save, such
  as numbering instances, also runs before a publish, and the in-use marker stays put.

**Finding: only the active scene is evaluated headless.** In background mode a shot
scene's `matrix_world` is stale until that scene is evaluated, so placement has to be
read from each object's own transform up its parent chain (or after evaluating that
scene's depsgraph). This matters for M5, which copies blocking from layout. Whether the
unsaved-changes flag survives a copy can't be checked headless (Python edits don't set
it); check it in the UI.

## T14. Animation links layout's shot node instead of copying it: pass (2026-11-11)

Run on 5.2.2 LTS and again on 5.3.0, same results. An animation file links a shot's node
(camera, an overridden character with blocking keys) from the layout publish and overrides
it: an override of layout's override. Then layout is republished with the camera and the
character moved and a prop added.

- Layout's camera move, character move and new prop all come through on reopening
  animation, with nothing broken; `instance_id` survives both levels of override.
- **Keys don't go straight onto layout's action**: it's linked, so Blender skips the key
  ("not editable") and the pose only sticks as a static override. Giving the rig a local
  copy of layout's action first works: blocking keeps playing and the animator's keys go
  on top. From then on that character no longer follows layout's blocking; characters the
  animator hasn't keyed still do.
- Animation publishes the overridden shot node with `libraries.write`; lighting links it
  and plays both the animator's keys and layout's blocking, three levels deep (rig, layout,
  animation), with nothing broken.
- A 10-shot animation file (a scene per shot, each linking and overriding its shot node, 3
  characters each) opens in a fresh Blender in about 0.03 s over Blender's own startup,
  with all 30 animated overrides and their actions loaded. Small generated rigs only;
  T4's heavy-rig numbers suggest overrides stay cheap.

So animation, per shot or per sequence, can link layout rather than copy it. M5 needs a
"start animating" step that gives a character a local copy of its action.
