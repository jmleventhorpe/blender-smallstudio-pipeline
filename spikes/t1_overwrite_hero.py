"""T1: can a hero file be overwritten while a shot that links it is open elsewhere?

Run by hand across machines, with the project on the NAS. Each step is one mode:

    prepare  publish crate v001 and save a shot linking it
    watch    open the shot and wait for the hero to change, reloading the library when it does
    publish  overwrite the hero with a new version (temp file, then replace, retried)
    local    all of the above on one machine, with watch in a second Blender

Two machines (A = Windows, then again with A = Linux):

    B:  blender -b --python spikes/t1_overwrite_hero.py -- prepare --project /mnt/nas/t1
    A:  blender P:/t1/shots/010_010_0010/animation/work/010_010_0010_animation_v001.blend
            --python spikes/t1_overwrite_hero.py -- watch --project P:/t1
        (A can also run with -b; the GUI is closer to real use. Start it from a terminal
        to see the output.)
    B:  blender -b --python spikes/t1_overwrite_hero.py -- publish --project /mnt/nas/t1 --version 2

One machine:

    blender -b --factory-startup --python spikes/t1_overwrite_hero.py -- local --project /mnt/nas/t1

Pass: the overwrite succeeds while the shot is open, a library reload in A shows the new
version, and reopening the shot shows it too.
If it fails, shots link versioned files and Check Updates rewrites library paths to latest.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# Line-buffered, so a watcher in another process reports as things happen.
sys.stdout.reconfigure(line_buffering=True)

import bmesh
import bpy

from spike_utils import (
    instance_collection,
    load_collection,
    open_file,
    start_file,
    step,
    write_publish,
)

ASSET = "crate"
MODELING = "assets/prop/crate/modeling"
SHOT = "shots/010_010_0010/animation/work/010_010_0010_animation_v001.blend"


def options() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "watch", "publish", "local"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=600.0, help="watch: seconds to wait")
    args = parser.parse_args(argv)
    args.project = args.project.resolve()
    return args


def hero_path(project: Path) -> Path:
    return project / MODELING / "publish/crate_modeling.blend"


def publish(project: Path, version: int) -> None:
    """Publish the crate with its size and publish_version both set to version."""
    start_file(project / MODELING / f"work/crate_modeling_v{version:03}.blend")
    root = bpy.data.collections.new(ASSET)
    bpy.context.scene.collection.children.link(root)
    root["pipeline_asset"] = ASSET
    root["publish_version"] = version
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=float(version))
    mesh = bpy.data.meshes.new(f"{ASSET}_geo")
    bm.to_mesh(mesh)
    bm.free()
    root.objects.link(bpy.data.objects.new(f"{ASSET}_geo", mesh))
    bpy.ops.wm.save_mainfile()

    hero = hero_path(project)
    versioned = hero.with_name(f"crate_modeling_v{version:03}.blend")
    start = time.perf_counter()
    write_publish(root, hero, versioned, mark=[root])
    print(f"T1 PUBLISHED v{version:03} in {time.perf_counter() - start:.2f}s -> {hero}")


def prepare(project: Path) -> None:
    step("Publish crate v001 and save a shot that links it")
    publish(project, version=1)
    start_file(project / SHOT)
    crate = load_collection(hero_path(project), ASSET)
    instance_collection(crate, ASSET, bpy.context.scene.collection)
    bpy.ops.wm.save_mainfile()
    print(f"T1 PREPARED shot at {project / SHOT}")


def linked_version() -> int | None:
    crate = next((c for c in bpy.data.collections if c.name == ASSET and c.library), None)
    return crate.get("publish_version") if crate else None


def reload_and_report(project: Path, seen_mtime: float) -> float:
    """Reload the crate's library if the hero changed on disk; return the mtime now."""
    hero = hero_path(project)
    try:
        mtime = hero.stat().st_mtime
    except OSError as error:  # Mid-replace on some shares.
        print(f"T1 hero not readable right now: {error}")
        return seen_mtime
    if mtime != seen_mtime:
        library = next(
            lib
            for lib in bpy.data.libraries
            if Path(bpy.path.abspath(lib.filepath)).name == hero.name
        )
        library.reload()
        print(f"T1 RELOADED: linked crate is now v{linked_version():03}")
    return mtime


def watch(project: Path, timeout: float) -> None:
    if not bpy.data.filepath:
        open_file(project / SHOT)
    start_version = linked_version()
    print(f"T1 WATCHING: shot open, linked crate is v{start_version:03}.")
    print("Publish from the other machine now.")
    seen = {"mtime": hero_path(project).stat().st_mtime}

    if not bpy.app.background:
        # In the UI, poll from a timer so Blender stays responsive.
        def poll() -> float | None:
            seen["mtime"] = reload_and_report(project, seen["mtime"])
            return None if linked_version() != start_version else 2.0

        bpy.app.timers.register(poll, first_interval=2.0)
        return

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and linked_version() == start_version:
        time.sleep(2.0)
        seen["mtime"] = reload_and_report(project, seen["mtime"])
    reloaded = linked_version()

    open_file(project / SHOT)
    reopened = linked_version()
    ok = reloaded != start_version and reopened == reloaded
    result = "PASS" if ok else "FAIL"
    print(
        f"T1 RESULT {result}: start v{start_version}, "
        f"after reload v{reloaded}, after reopen v{reopened}"
    )


def local(project: Path, version: int) -> None:
    prepare(project)
    step("Open the shot in a second Blender and watch")
    watcher = subprocess.Popen(
        [
            bpy.app.binary_path,
            "-b",
            "--factory-startup",
            str(project / SHOT),
            "--python",
            __file__,
            "--",
            "watch",
            "--project",
            str(project),
            "--timeout",
            "60",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    # Wait until the watcher has the shot open before overwriting.
    for line in watcher.stdout:
        print(f"   watcher: {line.rstrip()}")
        if line.startswith("T1 WATCHING"):
            break
    step(f"Overwrite the hero with v{version:03} while the shot is open")
    publish(project, version)
    for line in watcher.stdout:
        if line.startswith("T1 "):
            print(f"   watcher: {line.rstrip()}")
    watcher.wait()


def main() -> None:
    args = options()
    if args.mode == "prepare":
        prepare(args.project)
    elif args.mode == "watch":
        watch(args.project, args.timeout)
    elif args.mode == "publish":
        publish(args.project, args.version)
    else:
        local(args.project, args.version)


main()
