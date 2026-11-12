"""Loading: bringing publishes into a file and keeping them current.

core/ works out what's out of date (updates) and numbers instances (casting). blender/
links publishes and registers the project's Asset Browser library (libraries), reloads
changed ones (updates), keeps track of the asset instances in a scene and overrides one
where it stands (instances), and makes a linked asset a local copy to edit (editable), with
the Check Updates, Make Editable, Override and Back to Link actions.
"""
