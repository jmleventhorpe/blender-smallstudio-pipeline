"""Runs inside Blender (see run.py): the whole pipe, as an artist would drive it.

Assets are modelled, rigged and published; a set is dressed with a prop; layout blocks two
shots; animation animates on top; lighting renders a frame and comps it. Then changes are
made upstream (a prop republished, a camera moved, a shot added) and followed down to
lighting. Each stage's checks are small, so a failure says which stage broke.
"""

from typing import Any

import bpy
from conftest import (
    add_cube,
    give_material,
    key_x,
    make_cut,
    new_file,
    place,
    publish_cut,
    x_at,
)

from smallstudio_pipeline.loading.blender import instances
from smallstudio_pipeline.publishing.core.publishing import hero_record
from smallstudio_pipeline.shots.blender import layout


def new_asset_file(kind, name, task, asset="NEW"):
    """An empty file with an asset node made by New Node, saved as its workfile by Save To."""
    bpy.ops.wm.read_homefile(use_empty=True)
    new = {"asset_type": kind, "name": name} if asset == "NEW" else {}
    bpy.ops.pipeline.new_node(kind="ASSET", asset=asset, task=task, **new)
    bpy.ops.pipeline.save_to(category=kind, entity=name, task=task)
    return bpy.data.collections[name]


def publish():
    assert bpy.ops.pipeline.publish() == {"FINISHED"}


def select(scene, obj) -> Any:
    """Run the next operator with obj selected and active in scene, as clicking it would."""
    view_layer = scene.view_layers[0]
    for other in view_layer.objects:
        other.select_set(other == obj, view_layer=view_layer)
    # Typed loosely: the stubs miss temp_override's context-manager methods.
    return bpy.context.temp_override(
        scene=scene, view_layer=view_layer, active_object=obj, selected_objects=[obj]
    )


def broken():
    """Missing libraries or data, and overrides whose reference is gone."""
    found = [f"{lib.filepath} (missing)" for lib in bpy.data.libraries if lib.is_missing]
    for datablocks in (bpy.data.collections, bpy.data.objects, bpy.data.meshes):
        for datablock in datablocks:
            override = datablock.override_library
            if datablock.is_missing or (override and override.reference is None):
                found.append(datablock.name)
    return found


def hero_body(scene):
    """The hero's body as it stands in a shot: the mesh of its overridden instance."""
    (hero,) = [i for i in instances.instances(scene) if i.asset == "hero"]
    assert isinstance(hero.holder, bpy.types.Collection)
    return next(o for o in hero.holder.all_objects if o.type == "MESH")


def linked_body(scene):
    """The hero's body in a lighting scene, linked through animation."""
    return next(o for o in scene.objects if o.name == "body" and o.library is not None)


def strip_codes():
    return [layout.strip_shot(s) for s in layout.shot_strips(layout.master_scene())]


def test_the_whole_pipe(project):
    # Assets: the hero modelled and rigged, a crate, and the street set dressed with it.
    body = add_cube(new_asset_file("character", "hero", "model"), "body")
    give_material(body, "skin", (1, 0, 0, 1))
    publish()
    rig = new_asset_file("character", "hero", "rig", asset="hero")
    give_material(add_cube(rig, "body"), "skin", (0.5, 0.5, 0.5, 1))
    publish()
    skin = bpy.data.materials["skin"].diffuse_color
    assert list(skin[:]) == [1, 0, 0, 1]  # pyright: ignore[reportIndexIssue]  # The model's.

    add_cube(new_asset_file("prop", "crate", "model"), "crate_box")
    publish()
    new_asset_file("set", "street", "model")
    place(project, bpy.context.scene, "crate", location=(5.0, 0.0, 0.0))
    publish()
    street = hero_record(project.asset("street"), "model")
    assert street is not None and [(i.asset, i.location) for i in street.instances] == [
        ("crate", (5.0, 0.0, 0.0))
    ]

    # Layout: two shots on the street, the hero blocked in 0010.
    make_cut()
    bpy.ops.pipeline.add_shot()
    layout.master_scene().frame_current = 1000
    bpy.ops.pipeline.add_shot()
    first, second = bpy.data.scenes["010_010_0010"], bpy.data.scenes["010_010_0020"]
    for scene in (first, second):
        place(project, scene, "street")
    hero = place(project, first, "hero", task="rig")
    instances.override(hero, first, first.view_layers[0])
    key_x(hero_body(first), {101: 0, 148: 4})
    publish_cut()
    cast = project.shot("010_010_0010").metadata.casting
    assert sorted(entry.instance_id for entry in cast) == ["hero_01", "street_01"]
    assert project.shot("010_010_0020").frame_range == (101, 148)

    # Animation: the hero animated on top of its blocking.
    assert new_file("anim", "ANIMATION") == {"FINISHED"}
    first = bpy.data.scenes["010_010_0010"]
    body = hero_body(first)
    with select(first, body):
        assert bpy.ops.pipeline.animate() == {"FINISHED"}
    key_x(body, {120: 10})
    publish_cut()

    # Lighting: the animation plays, a frame renders, and comp reads it.
    assert new_file("light", "LIGHTING") == {"FINISHED"}
    lit, comp = bpy.data.scenes["010_010_0010"], bpy.data.scenes["010_010_0010.comp"]
    body = linked_body(lit)
    assert (x_at(body, lit, 120), x_at(body, lit, 148)) == (10.0, 4.0)
    for scene in (lit, comp):  # One tiny frame.
        scene.frame_end = scene.frame_start
        scene.render.resolution_percentage = 2
    lit.cycles.samples = 1  # pyright: ignore[reportAttributeAccessIssue]
    bpy.ops.render.render(animation=True, scene=lit.name)
    bpy.ops.render.render(animation=True, scene=comp.name)
    renders = project.root / "shots/010_010_0010/light/render/v001"
    assert (renders / "010_010_0010_light_v001_0101.exr").is_file()
    assert (renders / "comp/010_010_0010_comp_v001_0101.exr").is_file()
    bpy.ops.wm.save_mainfile()
    assert not broken()

    # A change to an asset: the crate, twice as tall, reaches lighting four links down.
    bpy.ops.wm.open_mainfile(filepath=str(project.asset("crate").workfile_path("model", 1)))
    for vertex in bpy.data.objects["crate_box"].data.vertices:  # pyright: ignore[reportAttributeAccessIssue]
        vertex.co.z *= 2
    publish()
    sequence = project.sequence("010_010")
    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("light", 1)))
    crate = next(o for o in bpy.data.objects if o.name == "crate_box")
    assert max(v.co.z for v in crate.data.vertices) == 1.0  # pyright: ignore[reportAttributeAccessIssue]

    # A change in layout: 0010's camera moves and a shot is added; animation and lighting follow.
    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("layout", 1)))
    camera = bpy.data.scenes["010_010_0010"].camera
    assert camera is not None
    camera.location.x = 5.0
    master = layout.master_scene()
    master.frame_current = 1000
    layout.add_shot(sequence, master, master.frame_current)
    publish_cut()

    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("anim", 1)))
    assert bpy.ops.pipeline.check_updates() == {"FINISHED"}
    assert strip_codes() == ["010_010_0010", "010_010_0020", "010_010_0030"]
    first = bpy.data.scenes["010_010_0010"]
    assert first.camera is not None and round(first.camera.location.x, 3) == 5.0
    assert x_at(hero_body(first), first, 120) == 10.0  # The animator's keys stay.
    bpy.ops.wm.save_mainfile()
    publish_cut()

    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("light", 1)))
    assert bpy.ops.pipeline.check_updates() == {"FINISHED"}
    assert strip_codes() == ["010_010_0010", "010_010_0020", "010_010_0030"]
    assert "010_010_0030.comp" in bpy.data.scenes
    lit = bpy.data.scenes["010_010_0010"]
    assert lit.camera is not None and round(lit.camera.location.x, 3) == 5.0
    assert x_at(linked_body(lit), lit, 120) == 10.0
    assert not broken()
