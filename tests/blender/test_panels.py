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

    def grid_flow(self, **_):
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
    for name in ("context", "shot", "loaded", "publish"):
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


def test_loaded_lists_each_instance_and_flags_newer_publishes(project, cut):
    from test_updates import republish_behind_the_files_back

    from smallstudio_pipeline.loading.blender.panels import LoadedPanel

    scene = bpy.data.scenes["010_010_0010"]
    shown = draw(LoadedPanel, scene)
    assert "hero_01" in shown and "hero · model v001" in shown and "out" not in shown

    republish_behind_the_files_back(project.asset("hero"), "new_hat")
    assert "v002 out" not in draw(LoadedPanel, scene)  # Not looked yet: no disk reads.
    bpy.ops.pipeline.refresh_versions()
    shown = draw(LoadedPanel, scene)
    assert "v002 out" in shown and "1 out of date" in shown

    path = "assets/character/hero/model/publish/hero_model.blend"
    bpy.ops.pipeline.update_publish(path=path)
    assert "out" not in draw(LoadedPanel, scene).replace("Update All", "")


def test_loaded_buttons_select_override_and_link_back(project, cut):
    scene = bpy.data.scenes["010_010_0010"]
    view_layer = scene.view_layers[0]
    empty = next(o for o in scene.objects if o.get("instance_id") == "hero_01")
    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(scene=scene, view_layer=view_layer):  # pyright: ignore[reportGeneralTypeIssues]
        assert bpy.ops.pipeline.select_instance(holder=empty.name) == {"FINISHED"}
        assert empty.select_get(view_layer=view_layer)
        assert bpy.ops.pipeline.override_for_posing(holder=empty.name) == {"FINISHED"}
        override = next(c for c in bpy.data.collections if c.override_library)
        assert bpy.ops.pipeline.back_to_link(holder=override.name) == {"FINISHED"}
    assert empty.instance_collection is not None and empty["instance_id"] == "hero_01"


def test_check_shows_what_an_asset_publish_would_write(project):
    from smallstudio_pipeline.publishing.blender import review
    from smallstudio_pipeline.publishing.blender.panels import PublishPanel

    publish_model(project)  # hero_model v001, from workfile v001, which stays open.
    assert "Published hero_model v001" in draw(PublishPanel)  # Until Check is pressed.
    assert bpy.ops.pipeline.check_publish() == {"FINISHED"}
    preview = review.current
    assert preview is not None and (preview.title, preview.writes) == (
        "hero · model",
        "hero_model v002",
    )
    assert "Replaces hero_model.blend (v001)" in preview.facts
    assert "Root hero: 1 object" in preview.facts
    shown = draw(PublishPanel)
    assert "hero_model v002" in shown and "Checks pass" in shown

    bpy.ops.pipeline.publish()
    assert review.current is None  # Written: Check again for the next.
    assert "Published hero_model v002" in draw(PublishPanel)


def test_check_lists_each_shot_and_what_changed(project, cut):
    from smallstudio_pipeline.publishing.blender import review
    from smallstudio_pipeline.publishing.blender.panels import PublishPanel

    bpy.ops.pipeline.check_publish()
    preview = review.current
    assert preview is not None and preview.writes == "010_010_layout v001"
    assert [(s.shot, s.cast, s.change) for s in preview.shots] == [
        ("0010", 1, "new"),
        ("0020", 0, "new"),
    ]
    bpy.ops.pipeline.publish()

    master = layout.master_scene()
    first, second = layout.shot_strips(master)
    second.right_handle_offset = 8  # Shorten 0020.
    master.sequence_editor.strips.remove(first)  # And drop 0010 by hand.
    bpy.ops.pipeline.check_publish()
    preview = review.current
    assert preview is not None and preview.writes == "010_010_layout v002"
    assert [(s.shot, s.change) for s in preview.shots] == [("0020", "retimed")]
    assert preview.omitted == ["0010"]
    shown = draw(PublishPanel)
    assert "0010 will be omitted" in shown and "retimed" in shown


def test_a_check_that_would_block_says_so_and_writes_nothing(project, cut):
    from smallstudio_pipeline.publishing.blender import results
    from smallstudio_pipeline.publishing.blender.panels import PublishPanel

    bpy.data.scenes["010_010_0010"].camera = None
    bpy.ops.pipeline.check_publish()
    assert results.last is not None and results.last.checked_only and not results.last.passed
    assert "Would be blocked: 010_010_0010" in draw(PublishPanel)
    assert not project.sequence("010_010").hero_path("layout").exists()


def test_the_old_results_panel_is_gone(registered):
    assert not hasattr(bpy.types, "PIPELINE_PT_results")
