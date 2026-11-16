"""Retarget a Mixamo FBX clip onto the Blocktop player rig.

Used by build_player.py for every FBX in blender/mixamo/. Download clips from
mixamo.com as: Format FBX Binary, Skin "Without Skin", 30 fps, and tick
"In Place" when offered (the game moves the player itself).

How it works: for each frame and each bone the source rotation *relative to
its rest pose* (in world space) is applied to the matching target bone's rest
pose. Both rigs rest in a T-pose, so bone rolls and axis conventions don't have
to match. Bone names are matched after stripping the "mixamorig:" prefix;
bones the target doesn't have (fingers, toe ends) are ignored. The Hips height
change is scaled by the ratio of hip heights.
"""
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


def retarget(src, target, f0, f1, action_name, in_place=True):
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
    scale = t_hip_rest.z / s_hip_rest.z if hips_src and s_hip_rest.z > 1e-6 else 1.0

    act = bpy.data.actions.new(action_name)
    act.use_fake_user = True
    target.animation_data_create()
    target.animation_data.action = act
    tw_rot = tw.to_3x3().normalized().to_quaternion()

    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        posed = {}  # target bone -> posed armature-space rotation
        for pb, sn in pairs:  # pose.bones is parent-before-child
            pb.rotation_mode = "QUATERNION"
            if sn:
                s_pose = (sw @ src.pose.bones[sn].matrix).to_3x3().normalized().to_quaternion()
                delta = s_pose @ s_rest[sn].inverted()
                world = delta @ t_rest[pb.name]
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
            pb.keyframe_insert("rotation_quaternion", frame=f)
        if hips_src:
            s_hip = (sw @ src.pose.bones[hips_src].matrix).translation
            d = (s_hip - s_hip_rest) * scale
            if in_place:
                d = Vector((0, 0, d.z))
            hb = target.pose.bones["Hips"]
            d_arm = tw.to_3x3().inverted() @ d
            hb.location = hb.bone.matrix_local.to_3x3().inverted() @ d_arm
            hb.keyframe_insert("location", frame=f)
    return act
