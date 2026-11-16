"""Self-check for retarget_mixamo.py (no Mixamo download needed).

Builds a Mixamo-style source rig (mixamorig: bone names, scrambled bone rolls,
1.3x size, moved off origin) playing the keyed Dunk, retargets it onto a fresh
player rig, and checks every frame that hands, feet and head land within 1 cm
of where the source puts them (scaled to the player's size). Then smoke-tests
the FBX import path.

    python blender/test_retarget.py
"""
import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_player as B  # noqa: E402
from retarget_mixamo import retarget, retarget_fbx  # noqa: E402

JOINTS = ["LeftHand", "RightHand", "LeftFoot", "RightFoot", "Head", "LeftForeArm", "RightLeg"]


def sample(arm, frames):
    sc = bpy.context.scene
    out = {}
    for f in frames:
        sc.frame_set(f)
        out[f] = {j: (arm.matrix_world @ arm.pose.bones[j].tail).copy() for j in JOINTS}
    return out


def sample_src(arm, frames):
    sc = bpy.context.scene
    out = {}
    for f in frames:
        sc.frame_set(f)
        out[f] = {j: (arm.matrix_world @ arm.pose.bones["mixamorig:" + j].tail).copy() for j in JOINTS}
    return out


def main():
    B.reset_scene()
    frames = list(range(1, 67))

    # Source: a Mixamo-like rig with scrambled bone rolls, scaled 1.3x, moved,
    # bones prefixed "mixamorig:". Keyed with the same clip (apply_pose is
    # roll-independent), so it performs the same motion at a different size.
    src = B.make_armature()
    src.name = "Source"
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.mode_set(mode="EDIT")
    for i, eb in enumerate(src.data.edit_bones):
        eb.roll = 0.7 * i - 2.0
    bpy.ops.object.mode_set(mode="OBJECT")
    act = B.keyed_clips(src)["Dunk"]
    src.animation_data.action = act
    for b in src.data.bones:
        b.name = "mixamorig:" + b.name
    src.scale = (1.3, 1.3, 1.3)
    src.location = (2.0, -1.0, 0.0)
    bpy.context.view_layer.update()

    # What the source actually does, mapped back to the target's size/place.
    # (Not `ref`: quaternion keys interpolate differently between keyframes
    # when bone rolls differ, so the two rigs only match exactly on keys.)
    ref = {f: {j: (p - src.location) / 1.3 for j, p in v.items()} for f, v in sample_src(src, frames).items()}

    tgt = B.make_armature()
    out = retarget(src, tgt, 1, 66, "DunkRT", in_place=True)
    tgt.animation_data.action = out
    src.animation_data.action = None
    got = sample(tgt, frames)
    worst = max((ref[f][j] - got[f][j]).length for f in frames for j in JOINTS)
    if "-v" in sys.argv:
        for f in frames:
            print(f, {j: round((ref[f][j] - got[f][j]).length * 100, 1) for j in JOINTS})
    print(f"retarget math: worst joint error {worst * 100:.2f} cm over {len(frames)} frames")

    # Smoke test of the FBX path (Blender's FBX exporter isn't lossless, so
    # this only checks that a Mixamo-named FBX imports and produces a clip).
    fbx = os.path.join(tempfile.mkdtemp(), "Dunk.fbx")
    src.animation_data.action = act
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"ARMATURE"},
                             add_leaf_bones=True, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False)
    clip = retarget_fbx(tgt, fbx, "DunkFBX")
    n = len(range(int(clip.frame_range[0]), int(clip.frame_range[1]) + 1))
    print(f"fbx import: {n} frames retargeted")
    if worst > 0.01 or n < 60:
        sys.exit(1)


if __name__ == "__main__":
    main()
