"""The pipeline's own publish checks, loaded by publish-validator.

Check files are loaded by path, so they can't import the add-on (its package name
depends on how it's installed). The Publish operator hands them what they need in
the subject's extras:

    asset, asset_type   the asset being published, from the project
    identity            (name, asset_type) from the root collection's properties, or None
    in_context          True when publishing from another asset's file
    file_entity         what the open file is for, e.g. "street"
    previous            {"version": 3, "label": "v003", "object_names": [...]} for the last
                        publish, or None
"""

import re

from publish_validator import WARNING, Check

INSTANCE_ID = "instance_id"
NUMBER_ENDING = re.compile(r"\.\d{3,}$")


class AssetRoot(Check):
    """The asset's root collection must say which asset it is, and be named after it.

    Shots find an asset's root by name when they link it, and the publish checks the
    root's identity against the project so a collection copied from another asset
    can't be published under the wrong name.
    """

    category = "Pipeline"
    hosts = ["blender"]

    def validate(self, ctx):
        extras = ctx.subject.extras
        root, asset = ctx.root, extras["asset"]
        if extras["identity"] is None:
            yield self.issue(f"{root.name} has no pipeline identity", root)
        elif extras["identity"] != (asset, extras["asset_type"]):
            name, asset_type = extras["identity"]
            yield self.issue(
                f"{root.name} says it's {asset_type} '{name}', but {asset} is a "
                f"{extras['asset_type']}",
                root,
            )
        if root.name != asset:
            yield self.issue(f"The root collection is called {root.name}, not {asset}", root)
        if extras["in_context"]:
            yield self.issue(
                f"Publishing {asset} from {extras['file_entity']}'s file", root, severity=WARNING
            )

    def fix(self, ctx, issues):
        ctx.root.name = ctx.subject.extras["asset"]


class InstanceIdDeclared(Check):
    """The root must declare an empty, overridable instance_id.

    Each instance in a shot fills it in. Library overrides drop custom properties their
    reference doesn't have, so it has to exist, empty, in the publish.
    """

    category = "Pipeline"
    hosts = ["blender"]

    def validate(self, ctx):
        root = ctx.root
        declared = root.get(INSTANCE_ID) == ""
        if not declared or not root.is_property_overridable_library(f'["{INSTANCE_ID}"]'):
            yield self.issue(f"{root.name} doesn't declare an overridable instance_id", root)

    def fix(self, ctx, issues):
        ctx.root[INSTANCE_ID] = ""
        ctx.root.property_overridable_library_set(f'["{INSTANCE_ID}"]', True)


class NoNumberEndings(Check):
    """Object and data names mustn't end in Blender's numbers, like crate.001.

    Shots match their edits (library overrides) to objects by name, so names must
    stay the same from publish to publish. Numbered names come and go as objects are
    copied and deleted. Give them their own names, without the dot.
    """

    category = "Pipeline"
    hosts = ["blender"]

    def validate(self, ctx):
        for obj in ctx.host.objects(ctx.root):
            if NUMBER_ENDING.search(obj.name):
                yield self.issue(f"{obj.name} ends in a Blender number", obj)
            data = getattr(obj, "data", None)
            if data is not None and NUMBER_ENDING.search(data.name):
                yield self.issue(f"{obj.name}'s data, {data.name}, ends in a Blender number", obj)


class StableNames(Check):
    """Objects in the last publish should still be there, with the same names.

    Shots match their edits to objects by name, so a renamed or deleted object loses
    whatever shots did to it. Fine if it's on purpose; check with animation first.
    """

    category = "Pipeline"
    hosts = ["blender"]
    severity = WARNING

    def validate(self, ctx):
        previous = ctx.subject.extras["previous"]
        if previous is None:
            return
        names = {obj.name for obj in ctx.host.objects(ctx.root)}
        for name in sorted(set(previous["object_names"]) - names):
            yield self.issue(f"{name} was in {previous['label']} but isn't now")
