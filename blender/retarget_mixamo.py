"""Retarget a Mixamo FBX clip onto the Blocktop player rig.

Used by build_player.py for every FBX in blender/mixamo/. Download clips from
mixamo.com as: Format FBX Binary, Skin "Without Skin", 30 fps, and tick
"In Place" when offered (the game moves the player itself).

How it works: for each frame and each bone the source rotation *relative to
its rest pose* (in world space) is applied to the matching target bone's rest
pose. Both rigs rest in a T-pose, so bone rolls and axis conventions don't have
to match. Bone names are matched after stripping the "mixamorig:" prefix;
bones the target doesn't have (fingers, toe ends) are ignored. The Hips height
height is taken above the clip's lowest ankle and scaled by leg length, so
rigs that rest with their hips at the origin (CMU BVH) work too.
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector


def _strip(name):
    return name.split(":")[-1].replace("mixamorig", "")


def retarget_fbx(target, fbx_path, action_name, in_place=True):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True, ignore_leaf_bones=True)
    new = [o for o in bpy.data.objects if o not in before]
    src = next(o for o in new if o.type == "ARMATURE")
    src_act = src.animation_data.action
    f0, f1 = (int(round(v)) for v in src_act.frame_range)
    act = retarget(src, target, f0, f1, action_name, in_place)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.actions.remove(src_act)
    return act


def retarget(src, target, f0, f1, action_name, in_place=True, step=1):
    sc = bpy.context.scene
    smap = {_strip(b.name): b.name for b in src.data.bones}
    tw = target.matrix_world
    sw = src.matrix_world
    pairs = [(pb, smap.get(pb.name)) for pb in target.pose.bones]

    # Rest orientations in world space.
    s_rest = {n: (sw @ src.data.bones[n].matrix_local).to_3x3().normalized().to_quaternion() for _, n in pairs if n}
    t_rest = {pb.name: (tw @ pb.bone.matrix_local).to_3x3().normalized().to_quaternion() for pb, _ in pairs}
    t_rest_arm = {pb.name: pb.bone.matrix_local.to_quaternion() for pb, _ in pairs}
    hips_src = smap.get("Hips")
    s_hip_rest = (sw @ src.data.bones[hips_src].matrix_local).translation if hips_src else Vector()
    t_hip_rest = (tw @ target.data.bones["Hips"].matrix_local).translation
    # Size ratio from leg length (hip joint to ankle), which works whether the
    # source rests standing (Mixamo) or with its hips at the origin (CMU BVH).
    def leg(arm, name, w):
        up, foot = arm.data.bones.get(name("LeftUpLeg")), arm.data.bones.get(name("LeftFoot"))
        return ((w @ up.head_local) - (w @ foot.head_local)).length if up and foot else 0.0
    s_leg = leg(src, lambda n: smap.get(n, ""), sw)
    t_leg = leg(target, lambda n: n, tw)
    scale = t_leg / s_leg if s_leg > 1e-6 else 1.0
    # Source "floor": the lowest ankle height over the clip (works for any rest pose).
    s_floor = None
    feet = [smap[n] for n in ("LeftFoot", "RightFoot") if n in smap]
    if feet:
        for f in range(f0, f1 + 1, step):
            sc.frame_set(f)
            z = min((sw @ src.pose.bones[n].head).z for n in feet)
            s_floor = z if s_floor is None else min(s_floor, z)
    else:
        s_floor = (sw @ src.data.bones[hips_src].head_local).z - s_leg if hips_src else 0.0
    t_floor = (tw @ target.data.bones["LeftFoot"].head_local).z

    # Facing: rigs can rest facing different ways (CMU BVH faces +Y, Mixamo and
    # the player face -Y). Turn the source's motion to the target's facing,
    # otherwise a leg swinging out on one rig swings in (crossed) on the other.
    def facing(arm, name, w):
        l, r = arm.data.bones.get(name("LeftUpLeg")), arm.data.bones.get(name("RightUpLeg"))
        if not (l and r):
            return None
        lat = (w @ l.head_local) - (w @ r.head_local)
        fwd = lat.cross(Vector((0, 0, 1)))  # left x up = forward
        return math.atan2(fwd.y, fwd.x)
    fs, ft = facing(src, lambda n: smap.get(n, ""), sw), facing(target, lambda n: n, tw)
    turn = Quaternion((0, 0, 1), ft - fs) if fs is not None and ft is not None else Quaternion()

    # Rest-pose differences (CMU rests with its legs spread ~20 degrees, the
    # player with legs straight down): per bone, the swing that turns the
    # target's rest direction into the source's, so each bone ends up pointing
    # the way the source bone points rather than copying a rest-relative turn.
    align = {}
    for pb, sn in pairs:
        if not sn:
            continue
        sb, tb = src.data.bones[sn], pb.bone
        sd = turn @ ((sw @ sb.tail_local) - (sw @ sb.head_local))
        td = (tw @ tb.tail_local) - (tw @ tb.head_local)
        align[pb.name] = td.rotation_difference(sd) if sd.length > 1e-6 and td.length > 1e-6 and pb.name != "Hips" else Quaternion()

    act = bpy.data.actions.new(action_name)
    act.use_fake_user = True
    target.animation_data_create()
    target.animation_data.action = act
    tw_rot = tw.to_3x3().normalized().to_quaternion()

    for f in range(f0, f1 + 1, step):
        kf = f if step == 1 else 1 + (f - f0) // step
        sc.frame_set(f)
        posed = {}  # target bone -> posed armature-space rotation
        for pb, sn in pairs:  # pose.bones is parent-before-child
            pb.rotation_mode = "QUATERNION"
            if sn:
                s_pose = (sw @ src.pose.bones[sn].matrix).to_3x3().normalized().to_quaternion()
                delta = turn @ s_pose @ s_rest[sn].inverted() @ turn.inverted()
                world = delta @ align[pb.name] @ t_rest[pb.name]
                q_arm = tw_rot.inverted() @ world
            else:
                par = pb.parent
                q_arm = (posed[par.name] @ t_rest_arm[par.name].inverted() if par else Quaternion()) @ t_rest_arm[pb.name]
            posed[pb.name] = q_arm
            r = t_rest_arm[pb.name]
            if pb.parent:
                pr = t_rest_arm[pb.parent.name]
                basis = r.inverted() @ pr @ posed[pb.parent.name].inverted() @ q_arm
            else:
                basis = r.inverted() @ q_arm
            pb.rotation_quaternion = basis.normalized()
            pb.keyframe_insert("rotation_quaternion", frame=kf)
        if hips_src:
            s_hip = (sw @ src.pose.bones[hips_src].matrix).translation
            # Height: hip height above the source's floor, scaled to the player.
            d = turn @ ((s_hip - s_hip_rest) * scale)
            d.z = (s_hip.z - s_floor) * scale - (t_hip_rest.z - t_floor)
            if in_place:
                d = Vector((0, 0, d.z))
            hb = target.pose.bones["Hips"]
            d_arm = tw.to_3x3().inverted() @ d
            hb.location = hb.bone.matrix_local.to_3x3().inverted() @ d_arm
            hb.keyframe_insert("location", frame=kf)
    return act
