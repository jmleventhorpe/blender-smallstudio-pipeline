"""Workfiles: what a file is, and saving it in the right place.

core/ works out a file's entity, task and version from its path (context), plans new
workfiles and the next free version (workfiles), and keeps in-use markers (inuse).
blender/ saves workfiles and holds the Open, New Workfile, Save To and Version Up
actions, and the Workfiles panel.
"""
