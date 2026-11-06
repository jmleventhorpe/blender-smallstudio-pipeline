"""Runs inside Blender (see run.py): the Pipeline tab's panels, drawn into a stand-in layout.

Blender doesn't draw panels headless, so each panel's draw() runs against FakeLayout,
which records every label and button, to check what the panel would show.
"""

from types import SimpleNamespace

import bpy
import pytest
from conftest import place, publish_model

from smallstudio_pipeline.interface.panels import ContextPanel
from smallstudio_pipeline.shots.blender import layout
from smallstudio_pipeline.shots.blender.panels import ShotPanel


class FakeLayout:
    """Stands in for a UILayout: every container returns itself, labels are recorded."""

    def __init__(self):
        self.texts = []
        self.alert = self.enabled = False

    def label(self, text="", **_):
        self.texts.append(text)

    def operator(self, idname, text="", **_):
        self.texts.append(f"[{text or idname}]")
        return SimpleNamespace()

    def row(self, **_):
        return self

    column = box = row

    def split(self, **_):
        return self


def draw(panel_class, scene=None):
    """What a panel shows, as one string."""
    fake = FakeLayout()
    context = SimpleNamespace(scene=scene or bpy.context.scene)
    panel_class.draw(SimpleNamespace(layout=fake), context)
    return " | ".join(fake.texts)


@pytest.fixture
def cut(project):
    publish_model(project)
    bpy.ops.pipeline.new_sequence(episode="NEW")
    bpy.ops.pipeline.add_shot()
    layout.master_scene().frame_current = 1000
    bpy.ops.pipeline.add_shot()
    place(project, bpy.data.scenes["010_010_0010"], "hero")
    bpy.ops.wm.save_mainfile()


def test_the_panels_are_in_both_sidebars(registered):
    for name in ("context", "shot"):
        for suffix in ("view3d", "sequencer"):
            assert hasattr(bpy.types, f"PIPELINE_PT_{name}_{suffix}")


def test_context_says_what_the_file_is_and_whats_on_show(project, cut):
    shown = draw(ContextPanel, bpy.data.scenes["010_010_0010"])
    assert "show" in shown and "010_010 · layout" in shown and "v001" in shown
    assert "shot 0010" in shown and "[Version Up]" in shown
    assert "the cut" in draw(ContextPanel, layout.master_scene())


def test_context_without_a_project_says_how_to_add_one(registered):
    shown = draw(ContextPanel)
    assert "None" in shown and "Preferences > Add-ons" in shown


def test_the_shot_panel_shows_the_shot_on_show(project, cut):
    shown = draw(ShotPanel, bpy.data.scenes["010_010_0010"])
    assert "010_010_0010" in shown and "101\N{EN DASH}148  (48)" in shown
    assert "1\N{EN DASH}48" in shown and "hero_01" in shown and "[pipeline.back_to_cut]" in shown


def test_in_the_cut_it_shows_the_selected_strip_or_asks_for_one(project, cut):
    master = layout.master_scene()
    strips = layout.shot_strips(master)
    for strip in strips:
        strip.select = strip == strips[1]
    master.sequence_editor.active_strip = strips[1]
    shown = draw(ShotPanel, master)
    assert "010_010_0020" in shown and "49\N{EN DASH}96" in shown and "nobody yet" in shown
    assert "[pipeline.go_to_shot]" in shown and bpy.ops.pipeline.go_to_shot.poll()

    master.sequence_editor.active_strip = None
    strips[1].select = False
    assert "Select a shot's strip" in draw(ShotPanel, master)


def test_the_shot_panel_only_shows_in_layout_files(project):
    project.create_asset("prop", "crate")
    bpy.ops.pipeline.new_workfile(category="prop", entity="crate", task="model")
    assert not ShotPanel.poll(bpy.context)
