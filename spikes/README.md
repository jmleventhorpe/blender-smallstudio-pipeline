# Spikes

Short scripts that check the Blender behaviour the design depends on, before any of the
tool is built. Each one builds its own tiny assets in an output folder, prints a PASS or
FAIL line per check and exits non-zero if anything failed. Results are in
[RESULTS.md](RESULTS.md).

Run from the repo root with Blender 5.3 (most were first run on 5.2; see RESULTS.md):

```bash
blender -b --factory-startup --python-exit-code 1 --python spikes/t2_link_overrides.py -- --out /tmp/t2
```

Leave out `--out` to use a new temp folder. Open the files it writes to look around.

| Script | Question |
| --- | --- |
| `t1_overwrite_hero.py` | Can a hero file be overwritten while a shot that links it is open, across machines? Run by hand; see its docstring. |
| `t2_link_overrides.py` | Can lighting link an animation file whose characters are library overrides? |
| `t3_libraries_write.py` | Does `libraries.write` publish cleanly from the open session, with asset marks on the hero only? |
| `t4_lighting_load.py` | How long does a sequence lighting file take to open at 10, 20 and 40 shots? Benchmark; use a real disk for `--out`. |
| `t5_nested_libraries.py` | Do lib pieces survive two levels of linking (lib, set, layout), with the set overridden in a shot for a tweak? |
| `t6_shared_character.py` | Can one file hold separate overrides of the same character in several scenes? |
| `t7_comp_from_exrs.py` | Can a comp scene read rendered EXRs and render without the 3D scene, through a shared group? |
| `t8_import_method.py` | Can a publish set an asset's Preferred Import Method from Python? |
| `t9_shot_settings.py` | Can per-shot property overrides on linked data be re-applied on load and render, including on a farm? (Fallback only; see T11.) |
| `t10_asset_previews.py` | Can a publish give the hero's asset a preview, headless? |
| `t11_scene_controls.py` | Can one shared, linked material render different values per shot, with no scripts? |
| `t13_layout_save_copy.py` | Can a sequence layout file be published as a Save Copy, with its scenes, cut, links and overrides intact? |
| `t14_link_layout.py` | Can animation link and override a shot's node from the layout publish, keep layout's later changes, and publish to lighting? |

T1 needs the NAS and two machines; its `local` mode runs every step on one machine.

`spike_utils.py` holds the shared pieces: a small skinned character, the animation and
lighting steps, and the checks.
