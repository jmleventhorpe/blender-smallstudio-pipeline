"""The pipeline's rules, with no Blender dependency.

From the bottom up: config (settings), naming and templates (names and paths), reading,
files and metadata (data on disk), tracker (where entity data comes from), project and
entities (what exists and where its files go). On top of those sit the modules the
Blender layer calls: context, workfiles, publishing, catalogs, updates and inuse.
"""
