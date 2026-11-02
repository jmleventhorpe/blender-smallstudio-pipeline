"""T3: does bpy.data.libraries.write publish cleanly from the open session?

Run:
    blender -b --factory-startup --python-exit-code 1 --python spikes/t3_libraries_write.py -- --out /tmp/t3

Pass: a written animation publish keeps its overrides and actions, links the rig by a
relative path and works in lighting; only the hero file carries an asset mark.
If it fails, publishing saves a full copy and cleans it, or moves to a background process.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy  # noqa: E402
from spike_utils import (  # noqa: E402
    CHARACTER,
    OUTPUT,
    Checks,
    asset_collections,
    broken_ids,
    build_animation,
    build_character,
    build_lighting,
    check_lighting,
    describe_libraries,
    find_object,
    open_file,
    output_dir,
    step,
    write_publish,
)

RIGGING = "assets/character/char/rigging"
ANIMATION = "shots/010_010_0010/animation"


def publish_rig(checks: Checks, out: Path, version: int, extra_bone: bool) -> Path:
    """Build a rigging workfile, then publish its root collection as hero and versioned copy."""
    work = out / f"{RIGGING}/work/char_rigging_v{version:03}.blend"
    hero = out / f"{RIGGING}/publish/char_rigging.blend"
    versioned = out / f"{RIGGING}/publish/char_rigging_v{version:03}.blend"

    collection = build_character(work, extra_bone=extra_bone)
    write_publish(collection, hero, versioned, mark=[collection])

    checks.check(
        "workfile session is left unmarked",
        collection.asset_data is None and not bpy.data.is_dirty,
        f"asset_data={collection.asset_data}, dirty={bpy.data.is_dirty}",
    )
    checks.check("hero is an asset", asset_collections(hero) == [CHARACTER], str(asset_collections(hero)))
    checks.check("versioned copy is not", asset_collections(versioned) == [], str(asset_collections(versioned)))
    checks.check("no temp file left behind", not any(hero.parent.glob("*.tmp.blend")))
    return hero


def check_written_publish(checks: Checks, path: Path) -> None:
    """Open a written animation publish and check what libraries.write kept."""
    open_file(path)
    describe_libraries()
    print(f"   scenes in file: {[s.name for s in bpy.data.scenes]}")

    output = bpy.data.collections.get(OUTPUT)
    checks.check("output collection is in the publish", output is not None)
    character = next(c for c in output.children if c.get("pipeline_asset") == CHARACTER)
    checks.check(
        "character is still a local override",
        character.library is None and character.override_library is not None,
    )
    rig = find_object(character, "ARMATURE")
    action = rig.animation_data.action if rig.animation_data else None
    checks.check("action is in the publish", action is not None, getattr(action, "name", ""))
    checks.check("instance_id kept", character.get("instance_id") == f"{CHARACTER}_01")

    libraries = list(bpy.data.libraries)
    checks.check(
        "rig is linked by a relative path",
        len(libraries) == 1 and libraries[0].filepath.startswith("//") and not libraries[0].is_missing,
        ", ".join(lib.filepath for lib in libraries),
    )
    broken = broken_ids()
    checks.check("no missing data or broken overrides", not broken, ", ".join(broken))

    # Anything the publish didn't need would show up here.
    local_objects = sorted(obj.name for obj in bpy.data.objects if obj.library is None)
    print(f"   local objects: {local_objects}")


def main() -> None:
    out = output_dir()
    checks = Checks("T3")
    anim_work = out / f"{ANIMATION}/work/010_010_0010_animation_v001.blend"
    anim_hero = out / f"{ANIMATION}/publish/010_010_0010_animation.blend"
    anim_versioned = out / f"{ANIMATION}/publish/010_010_0010_animation_v001.blend"
    lighting = out / "sequences/010_010/lighting/work/010_010_lighting_v001.blend"

    step("Rigging: publish v001 from the workfile (hero marked, versioned copy unmarked)")
    rig_hero = publish_rig(checks, out, version=1, extra_bone=False)

    step("Animation: build the workfile against the rig hero")
    expected = build_animation(anim_work, rig_hero)

    step("Animation: publish the output collection with libraries.write")
    write_publish(bpy.data.collections[OUTPUT], anim_hero, anim_versioned)

    step("Open the written publish")
    check_written_publish(checks, anim_hero)

    step("Lighting: link the written publish")
    build_lighting(lighting, anim_hero)
    check_lighting(checks, lighting, expected, expect_tail=False)

    step("Rigging: publish v002 with an extra bone, then reopen lighting")
    publish_rig(checks, out, version=2, extra_bone=True)
    check_lighting(checks, lighting, expected, expect_tail=True)

    checks.finish()


main()
