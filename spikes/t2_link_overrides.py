"""T2: can lighting link an animation file whose characters are library overrides?

Run:
    blender -b --factory-startup --python-exit-code 1 --python spikes/t2_link_overrides.py -- --out /tmp/t2

Pass: the animation plays in lighting, a rig republish comes through, nothing reports
broken overrides. If it fails, animation publishes switch to caches for lighting.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from spike_utils import (  # noqa: E402
    Checks,
    build_animation,
    build_character,
    build_lighting,
    check_lighting,
    output_dir,
    step,
)


def main() -> None:
    out = output_dir()
    checks = Checks("T2")
    rig_path = out / "assets/character/char/rigging/publish/char_rigging.blend"
    anim_path = out / "shots/010_010_0010/animation/work/010_010_0010_animation_v001.blend"
    lighting_path = out / "sequences/010_010/lighting/work/010_010_lighting_v001.blend"

    step("Build the rig")
    build_character(rig_path)

    step("Animation: link and override the rig, key poses, gather into an output collection")
    expected = build_animation(anim_path, rig_path)

    step("Lighting: link the output collection from the animation file")
    build_lighting(lighting_path, anim_path)
    check_lighting(checks, lighting_path, expected, expect_tail=False)

    step("Republish the rig with an extra bone, then reopen lighting")
    build_character(rig_path, extra_bone=True)
    check_lighting(checks, lighting_path, expected, expect_tail=True)

    checks.finish()


main()
