"""T8: can a publish set an asset's Preferred Import Method from Python?

Run:
    blender -b --factory-startup --python-exit-code 1 --python spikes/t8_import_method.py -- --out /tmp/t8

Pass: the hero's asset carries Preferred Import Method = Link; the versioned copy has no
asset data. Dragging from the Asset Browser can only be checked by hand, in the UI.
If it fails, artists set the Asset Browser's import method to Link once, in preferences.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy  # noqa: E402
from spike_utils import (  # noqa: E402
    CHARACTER,
    Checks,
    build_character,
    load_collection,
    open_file,
    output_dir,
    start_file,
    step,
    write_publish,
)


def main() -> None:
    out = output_dir()
    checks = Checks("T8")
    folder = out / "assets/character/char/rigging"
    hero = folder / "publish/char_rigging.blend"
    versioned = folder / "publish/char_rigging_v001.blend"

    step("Publish the rig: hero marked with Preferred Import Method = Link")
    collection = build_character(folder / "work/char_rigging_v001.blend")
    write_publish(collection, hero, versioned, mark=[collection])

    step("Open the hero")
    open_file(hero)
    asset = bpy.data.collections[CHARACTER].asset_data
    checks.check("hero root is an asset", asset is not None)
    checks.check(
        "hero asks to be linked",
        asset is not None
        and asset.use_preferred_import_method
        and asset.preferred_import_method == "LINK",
        f"use={getattr(asset, 'use_preferred_import_method', None)}, "
        f"method={getattr(asset, 'preferred_import_method', None)}",
    )

    step("Open the versioned copy")
    open_file(versioned)
    checks.check("versioned copy has no asset data", bpy.data.collections[CHARACTER].asset_data is None)

    step("Link the hero into a shot and read the setting from the library")
    start_file(out / "shots/010_010_0010/animation/work/010_010_0010_animation_v001.blend")
    linked = load_collection(hero, CHARACTER)
    method = linked.asset_data.preferred_import_method if linked.asset_data else None
    checks.check("setting is readable on linked data", method == "LINK", repr(method))

    checks.finish()


main()
