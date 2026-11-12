"""The pipeline's own publish checks, loaded by publish-validator.

Check files are loaded by path, so they can't import the add-on (its package name
depends on how it's installed). The Publish operator hands them what they need in
the subject's extras. An asset publish has one subject, its root collection:

    entity_kind         "asset"
    asset, asset_type   the asset being published, from the project
    identity            (name, asset_type) from the root collection's properties, or None
    previous            {"version": 3, "label": "v003", "object_names": [...]} for the last
                        publish, or None

A layout or animation publish has a subject per shot, its scene's collection:

    entity_kind         "shot"
    shot, scene         the shot's code, and its scene
    instances           [(what holds the instance ID, asset name)] standing in the shot
    known_assets        the names of the project's assets
    layout_cast         animation only: [(asset, instance ID)] layout last published
"""

import re

from publish_validator import WARNING, Check

INSTANCE_ID = "instance_id"
NUMBER_ENDING = re.compile(r"\.\d{3,}$")


class AssetCheck(Check):
    """Base for checks on asset publishes; shots skip them."""

    abstract = True
    category = "Pipeline"
    hosts = ["blender"]

    @classmethod
    def applies_to(cls, host_name, subject):
        kind = subject.extras.get("entity_kind", "asset")
        return kind == "asset" and super().applies_to(host_name, subject)


class ShotCheck(Check):
    """Base for checks on each shot of a layout publish."""

    abstract = True
    category = "Shots"
    hosts = ["blender"]

    @classmethod
    def applies_to(cls, host_name, subject):
        kind = subject.extras.get("entity_kind")
        return kind == "shot" and super().applies_to(host_name, subject)


class AssetRoot(AssetCheck):
    """The asset's root collection must say which asset it is, and be named after it.

    Shots find an asset's root by name when they link it, and the publish checks the
    root's identity against the project so a collection copied from another asset
    can't be published under the wrong name.
    """

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

    def fix(self, ctx, issues):
        ctx.root.name = ctx.subject.extras["asset"]


class InstanceIdDeclared(AssetCheck):
    """The root must declare an empty, overridable instance_id.

    Each instance in a shot fills it in. Library overrides drop custom properties their
    reference doesn't have, so it has to exist, empty, in the publish.
    """

    def validate(self, ctx):
        root = ctx.root
        declared = root.get(INSTANCE_ID) == ""
        if not declared or not root.is_property_overridable_library(f'["{INSTANCE_ID}"]'):
            yield self.issue(f"{root.name} doesn't declare an overridable instance_id", root)

    def fix(self, ctx, issues):
        ctx.root[INSTANCE_ID] = ""
        ctx.root.property_overridable_library_set(f'["{INSTANCE_ID}"]', True)


class NoNumberEndings(AssetCheck):
    """Object and data names mustn't end in Blender's numbers, like crate.001.

    Shots match their edits (library overrides) to objects by name, so names must
    stay the same from publish to publish. Numbered names come and go as objects are
    copied and deleted. Give them their own names, without the dot.
    """

    def validate(self, ctx):
        for obj in ctx.host.objects(ctx.root):
            if NUMBER_ENDING.search(obj.name):
                yield self.issue(f"{obj.name} ends in a Blender number", obj)
            data = getattr(obj, "data", None)
            if data is not None and NUMBER_ENDING.search(data.name):
                yield self.issue(f"{obj.name}'s data, {data.name}, ends in a Blender number", obj)


class StableNames(AssetCheck):
    """Objects in the last publish should still be there, with the same names.

    Shots match their edits to objects by name, so a renamed or deleted object loses
    whatever shots did to it. Fine if it's on purpose; check with animation first.
    """

    severity = WARNING

    def validate(self, ctx):
        previous = ctx.subject.extras["previous"]
        if previous is None:
            return
        names = {obj.name for obj in ctx.host.objects(ctx.root)}
        for name in sorted(set(previous["object_names"]) - names):
            yield self.issue(f"{name} was in {previous['label']} but isn't now")


class ShotCamera(ShotCheck):
    """Each shot's scene needs a camera.

    The cut shows each shot through its scene's camera, and animation copies it from
    layout. Add Shot gives every shot one; set the scene's camera if it was removed.
    """

    def validate(self, ctx):
        scene = ctx.subject.extras["scene"]
        if scene.camera is None:
            yield self.issue(f"Shot {ctx.subject.extras['shot']} has no camera")


class UniqueInstanceIds(ShotCheck):
    """Every asset instance in a shot needs its own instance ID.

    Animation and lighting find each instance by its ID, never by its Blender name.
    Duplicating an instance (Shift+D) copies its ID too; Fix gives the copies new ones.
    """

    def validate(self, ctx):
        seen = {}
        for holder, _asset in ctx.subject.extras["instances"]:
            instance_id = holder.get(INSTANCE_ID, "")
            if not instance_id:
                yield self.issue(f"{holder.name} has no instance ID; save the file", holder)
            elif instance_id in seen:
                yield self.issue(
                    f"{holder.name} has the same instance ID as {seen[instance_id].name} "
                    f"({instance_id})",
                    holder,
                )
            else:
                seen[instance_id] = holder

    def fix(self, ctx, issues):
        instances = ctx.subject.extras["instances"]
        highest = {}
        for holder, asset in instances:
            number = _instance_number(asset, holder.get(INSTANCE_ID, ""))
            highest[asset] = max(highest.get(asset, 0), number or 0)
        seen = set()
        for holder, asset in sorted(instances, key=lambda pair: pair[0].name):
            instance_id = holder.get(INSTANCE_ID, "")
            if not instance_id or instance_id in seen:
                highest[asset] += 1
                instance_id = f"{asset}_{highest[asset]:02d}"
                holder[INSTANCE_ID] = instance_id
            seen.add(instance_id)


class KnownAssets(ShotCheck):
    """Every instance in a shot must be an asset in this project.

    A shot's casting is recorded by asset name, so an instance of an asset that was
    renamed or removed, or linked from another project, can't be cast.
    """

    def validate(self, ctx):
        known = ctx.subject.extras["known_assets"]
        for holder, asset in ctx.subject.extras["instances"]:
            if asset not in known:
                yield self.issue(f"{holder.name} is {asset}, which isn't an asset here", holder)


class CastMatchesLayout(ShotCheck):
    """In animation, a shot's cast should be the one layout published.

    Layout decides who's in a shot; lighting and the edit read the cast layout recorded.
    Add or remove a character in layout and publish it, and the animation file follows.
    """

    severity = WARNING

    @classmethod
    def applies_to(cls, host_name, subject):
        return "layout_cast" in subject.extras and super().applies_to(host_name, subject)

    def validate(self, ctx):
        wanted = {instance_id for _asset, instance_id in ctx.subject.extras["layout_cast"]}
        here = {}
        for holder, _asset in ctx.subject.extras["instances"]:
            here[holder.get(INSTANCE_ID, "")] = holder
        for instance_id, holder in sorted(here.items()):
            if instance_id and instance_id not in wanted:
                yield self.issue(f"{instance_id} isn't in layout's cast for this shot", holder)
        for instance_id in sorted(wanted - set(here)):
            yield self.issue(f"{instance_id} is in layout's cast but not here")


def _instance_number(asset, instance_id):
    """3 for "crate_03" (the same rule as the add-on's loading/core/casting.py)."""
    name, _, number = instance_id.rpartition("_")
    return int(number) if name == asset and number.isdigit() else None
