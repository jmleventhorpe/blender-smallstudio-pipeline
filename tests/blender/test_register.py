"""Runs inside Blender (see run.py): the add-on registers and unregisters cleanly."""

import bpy

import smallstudio_pipeline


def test_runs_on_blender_5_3():
    assert bpy.app.version[:2] == (5, 3)


def test_register_and_unregister():
    smallstudio_pipeline.register()
    smallstudio_pipeline.unregister()
