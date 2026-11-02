# Spikes

Short scripts that check the Blender behaviour the design depends on, before any of the
tool is built. Each one builds its own tiny assets in an output folder, prints a PASS or
FAIL line per check and exits non-zero if anything failed. Results are in
[RESULTS.md](RESULTS.md).

Run from the repo root with Blender 5.2:

```bash
blender -b --factory-startup --python-exit-code 1 --python spikes/t2_link_overrides.py -- --out /tmp/t2
```

Leave out `--out` to use a new temp folder. Open the files it writes to look around.

| Script | Question |
| --- | --- |
| `t2_link_overrides.py` | Can lighting link an animation file whose characters are library overrides? |
| `t3_libraries_write.py` | Does `libraries.write` publish cleanly from the open session, with asset marks on the hero only? |
| `t5_nested_libraries.py` | Do lib pieces survive two levels of linking (lib, set, layout), with the set overridden in a shot for a tweak? |
| `t6_shared_character.py` | Can one file hold separate overrides of the same character in several scenes? |
| `t7_comp_from_exrs.py` | Can a comp scene read rendered EXRs and render without the 3D scene, through a shared group? |
| `t8_import_method.py` | Can a publish set an asset's Preferred Import Method from Python? |

Still to come: T1 (overwriting a linked hero over the NAS, run by hand on two machines)
and T4 (sequence lighting load time at 10, 20 and 40 shots).

`spike_utils.py` holds the shared pieces: a small skinned character, the animation and
lighting steps, and the checks.
