"""Publishing: checking what a workfile makes, then writing it for other files to link.

core/ decides what a publish is and records it (publishing) and keeps the Asset Browser's
catalogs (catalogs). blender/ writes asset publishes with thumbnails (assets) and layout
publishes (layout), publishes from inside another asset's file (in_context), keeps a
rig's materials in step with its model (materials), sets up publish-validator
(validation) and shows its results in the sidebar (results), with the Publish action.
checks/ and validation.toml are the pipeline's own checks and settings.
"""
