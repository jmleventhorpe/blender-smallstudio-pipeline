"""Runs inside Blender (see run.py): the Pipeline tab's panels, drawn into a stand-in layout.

Blender doesn't draw panels headless, so each panel's draw() runs against FakeLayout,
which records every label and button, to check what the panel would show.
"""

from types import SimpleNamespace

import bpy
import pytest
from conftest import make_cut, place, publish_model

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

    def prop(self, data, name, **_):
        self.texts.append(f"<{name}: {getattr(data, name)}>")

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
    scene = scene or bpy.context.scene
    view_layer = bpy.context.view_layer if scene == bpy.context.scene else scene.view_layers[0]
    context = SimpleNamespace(
        scene=scene,
        view_layer=view_layer,
        selected_objects=[o for o in view_layer.objects if o.select_get(view_layer=view_layer)],
        window_manager=bpy.context.window_manager,
        workspace=None,
    )
    panel_class.draw(SimpleNamespace(layout=fake), context)
    return " | ".join(fake.texts)


@pytest.fixture
def cut(project):
    publish_model(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    layout.master_scene().frame_current = 1000
    bpy.ops.pipeline.add_shot()
    place(project, bpy.data.scenes["010_010_0010"], "hero")
    bpy.ops.wm.save_mainfile()


def test_the_panels_are_in_both_sidebars(registered):
    for name in ("context", "nodes", "shot", "publish"):
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


def test_in_the_cut_the_shot_panel_says_so(project, cut):
    master = layout.master_scene()
    for strip in layout.shot_strips(master):
        strip.select = True  # Selecting strips doesn't choose a shot any more.
    shown = draw(ShotPanel, master)
    assert "You're in the cut" in shown and "010_010_0020" not in shown


def test_the_shot_panel_only_shows_in_layout_files(project):
    project.create_asset("prop", "crate")
    bpy.ops.pipeline.new_workfile(category="prop", entity="crate", task="model")
    assert not ShotPanel.poll(bpy.context)


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


def test_workfiles_lists_a_tasks_versions_newest_first(project):
    from conftest import save_blend

    from smallstudio_pipeline.workfiles.blender.panels import WorkfilesPanel, listing

    hero = project.create_asset("character", "hero")
    save_blend(hero.workfile_path("model", 1))
    save_blend(hero.workfile_path("model", 2))
    choices = bpy.context.window_manager.pipeline_browse
    choices.category = "character"
    choices.entity = "hero"
    choices.task = "model"
    assert [(version, name) for version, name, _ in listing] == [
        (2, "hero_model_v002.blend"),
        (1, "hero_model_v001.blend"),
    ]
    shown = draw(WorkfilesPanel)
    assert "hero_model_v002.blend" in shown and "[pipeline.open]" in shown

    choices.task = "rig"
    assert listing == [] and "No workfiles yet" in draw(WorkfilesPanel)


def test_publish_shows_the_node_and_what_it_becomes_before_any_check(project):
    from smallstudio_pipeline.publishing.blender.panels import PublishPanel

    publish_model(project)
    shown = draw(PublishPanel)
    assert "Node | hero" in shown and "hero · model" in shown and "hero_model v002" in shown


def test_in_a_layout_file_a_shots_root_publishes_its_sequence_first(project, cut):
    from smallstudio_pipeline.publishing.blender import review
    from smallstudio_pipeline.publishing.blender.panels import PublishPanel

    master = layout.master_scene()
    assert "Node | 010_010 | Publishes | 010_010 · layout" in draw(PublishPanel, master)
    shot = bpy.data.scenes["010_010_0020"]
    assert "Node | 010_010_0020 | Publishes | 010_010 · layout" in draw(PublishPanel, shot)

    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(scene=shot, view_layer=shot.view_layers[0]):  # pyright: ignore[reportGeneralTypeIssues]
        bpy.ops.pipeline.check_publish()
    assert review.current is not None and review.current.highlight == "0020"
    assert [row.shot for row in review.current.shots] == ["0020", "0010"]
