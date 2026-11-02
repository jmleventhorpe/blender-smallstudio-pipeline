"""Runs inside Blender (see run.py): the add-on registers and unregisters cleanly."""

import bpy

import smallstudio_pipeline


def test_runs_on_blender_5_2():
    assert bpy.app.version[:2] == (5, 2)


def test_register_and_unregister():
    smallstudio_pipeline.register()
    smallstudio_pipeline.unregister()
