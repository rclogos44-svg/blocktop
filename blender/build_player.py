"""Build the Blocktop blocky player in Blender and export assets/player.glb.

Run with either:
    blender -b -P blender/build_player.py
    python blender/build_player.py          (with `pip install bpy`)

What it makes:
  * An armature with Mixamo bone names (Hips, Spine, LeftArm, ...) in a T-pose,
    so Mixamo clips map onto it bone-for-bone.
  * A blocky body (boxes, one bone each) using the same proportions as the
    in-game player (computeDims in index.html), for a 6'6" / 210 lb wing.
  * Hand-keyed clips: Idle, Run, Dribble, Crossover, Jumper, Dunk.
  * Any FBX dropped in blender/mixamo/ (e.g. Dribble.fbx) is retargeted onto
    the rig and replaces the keyed clip of the same name (or adds a new one).

All clips are in place: the game moves the player, the clips only animate the
body (the Hips bone still moves up and down for jumps).
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from retarget_mixamo import retarget_fbx  # noqa: E402

OUT = os.path.join(REPO, "assets", "player.glb")
MIXAMO_DIR = os.path.join(HERE, "mixamo")
FPS = 30

# ---------------------------------------------------------------- proportions
# Same formulas as Player.computeDims() in index.html.
H = 78 * 0.0254          # height 6'6"
WS = 5 * 0.0254          # wingspan over height
BULK = 1.0
THIGH, SHIN, FOOT = 0.245 * H, 0.225 * H, 0.035 * H
HIP = THIGH + SHIN + FOOT
TORSO, NECK, HEAD = 0.3 * H, 0.045 * H, 0.125 * H
SHW = 0.225 * H * BULK
ARM = (H + WS - SHW) / 2
UARM, FARM, HAND = ARM * 0.42, ARM * 0.38, ARM * 0.2
SHOULDER_Z = HIP + 0.03 * H + 0.94 * TORSO
NECK_Z = HIP + 0.03 * H + TORSO
TW = 0.078 * H * BULK    # leg thickness
HIPW = SHW * 0.8
HIPD = 0.115 * H * BULK
LEGX = HIPW * 0.26

# ------------------------------------------------------------------- helpers

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    return sc


def make_armature():
    data = bpy.data.armatures.new("PlayerRig")
    arm = bpy.data.objects.new("Player", data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones

    def bone(name, head, tail, parent=None, roll=0.0, connect=False):
        b = eb.new(name)
        b.head, b.tail, b.roll = Vector(head), Vector(tail), roll
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        return b

    # Character faces -Y (Blender front view); glTF export turns that into +Z.
    z0 = HIP + 0.03 * H
    bone("Hips", (0, 0, HIP), (0, 0, z0))
    bone("Spine", (0, 0, z0), (0, 0, z0 + TORSO * 0.36), "Hips", connect=True)
    bone("Spine1", (0, 0, z0 + TORSO * 0.36), (0, 0, z0 + TORSO * 0.66), "Spine", connect=True)
    bone("Spine2", (0, 0, z0 + TORSO * 0.66), (0, 0, NECK_Z), "Spine1", connect=True)
    bone("Neck", (0, 0, NECK_Z), (0, 0, NECK_Z + NECK), "Spine2", connect=True)
    bone("Head", (0, 0, NECK_Z + NECK), (0, 0, NECK_Z + NECK + HEAD), "Neck", connect=True)
    for side, s in (("Left", 1), ("Right", -1)):
        sx = s * SHW / 2
        bone(f"{side}Shoulder", (s * 0.04, 0, SHOULDER_Z - 0.03), (sx, 0, SHOULDER_Z), "Spine2")
        bone(f"{side}Arm", (sx, 0, SHOULDER_Z), (sx + s * UARM, 0, SHOULDER_Z), f"{side}Shoulder", connect=True)
        bone(f"{side}ForeArm", (sx + s * UARM, 0, SHOULDER_Z), (sx + s * (UARM + FARM), 0, SHOULDER_Z), f"{side}Arm", connect=True)
        bone(f"{side}Hand", (sx + s * (UARM + FARM), 0, SHOULDER_Z), (sx + s * ARM, 0, SHOULDER_Z), f"{side}ForeArm", connect=True)
        lx = s * LEGX
        bone(f"{side}UpLeg", (lx, 0, HIP), (lx, 0, HIP - THIGH), "Hips")
        bone(f"{side}Leg", (lx, 0, HIP - THIGH), (lx, 0, FOOT), f"{side}UpLeg", connect=True)
        bone(f"{side}Foot", (lx, 0, FOOT), (lx, -0.06 * H, FOOT * 0.3), f"{side}Leg", connect=True)
        bone(f"{side}ToeBase", (lx, -0.06 * H, FOOT * 0.3), (lx, -0.1 * H, FOOT * 0.3), f"{side}Foot", connect=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def make_materials():
    def mat(name, rgb, rough=0.8):
        m = bpy.data.materials.new(name)
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
        bsdf.inputs["Roughness"].default_value = rough
        return m
    # Names matter: the game/viewer recolors by material name.
    return {
        "Skin": mat("Skin", (0.42, 0.24, 0.14)),
        "Jersey": mat("Jersey", (0.03, 0.12, 0.85)),
        "Shorts": mat("Shorts", (0.02, 0.06, 0.45)),
        "Trim": mat("Trim", (1.0, 0.85, 0.2)),
        "Sock": mat("Sock", (0.9, 0.9, 0.9)),
        "Shoe": mat("Shoe", (0.05, 0.05, 0.05), 0.5),
        "Eyes": mat("Eyes", (0.02, 0.02, 0.02), 0.3),
    }


def make_body(arm, mats):
    """Rigid blocky body: every box is weighted 100% to one bone."""
    names = list(mats)
    verts, faces, face_mats, groups = [], [], [], {}

    def box(bone, center, size, m):
        """size is (width, height, depth) like THREE.BoxGeometry; Blender is Z-up."""
        cx, cy, cz = center
        hx, hz, hy = (v / 2 for v in size)
        base = len(verts)
        for dx in (-1, 1):
            for dy in (-1, 1):
                for dz in (-1, 1):
                    verts.append((cx + dx * hx, cy + dy * hy, cz + dz * hz))
        idx = [base + i for i in range(8)]
        groups.setdefault(bone, []).extend(idx)
        # vertex i = (dx,dy,dz) bits 4,2,1
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            faces.append(tuple(base + i for i in f))
            face_mats.append(names.index(m))

    z0 = HIP + 0.03 * H
    # pelvis / torso
    box("Hips", (0, 0, HIP + 0.01 * H), (HIPW, 0.1 * H, HIPD), "Shorts")
    box("Hips", (0, 0, HIP - 0.035 * H), (HIPW * 1.01, 0.012 * H, HIPD * 1.01), "Trim")  # waistband
    box("Spine", (0, 0, z0 + TORSO * 0.18), (HIPW * 1.02, TORSO * 0.36, HIPD), "Jersey")
    for b, z_a, z_b in (("Spine1", 0.36, 0.66), ("Spine2", 0.66, 1.0)):
        box(b, (0, 0, z0 + TORSO * (z_a + z_b) / 2), (SHW, TORSO * (z_b - z_a), 0.125 * H), "Jersey")
    box("Spine2", (0, -0.0625 * H, NECK_Z - 0.01), (SHW * 0.35, 0.02, 0.006), "Trim")  # collar
    for s in (1, -1):  # side stripes
        box("Spine1", (s * SHW / 2, 0, z0 + TORSO * 0.51), (0.006, TORSO * 0.3, 0.06), "Trim")
    box("Neck", (0, 0, NECK_Z + NECK * 0.45), (0.055 * H, NECK * 1.3, 0.055 * H), "Skin")
    hz = NECK_Z + NECK
    box("Head", (0, 0, hz + HEAD / 2), (0.09 * H, HEAD, 0.105 * H), "Skin")
    box("Head", (0, 0, hz + HEAD * 0.8), (0.092 * H, HEAD * 0.14, 0.107 * H), "Trim")  # headband
    for s in (1, -1):
        box("Head", (s * 0.02 * H, -0.0525 * H - 0.004, hz + HEAD * 0.56), (0.013 * H, 0.011 * H, 0.012), "Eyes")
    # arms (T-pose along X)
    for side, s in (("Left", 1), ("Right", -1)):
        sx = s * SHW / 2
        aw = 0.05 * H * BULK
        box(f"{side}Shoulder", (sx - s * 0.02, 0, SHOULDER_Z), (0.08, aw * 1.25, aw * 1.25), "Skin")
        box(f"{side}Arm", (sx + s * UARM / 2, 0, SHOULDER_Z), (UARM, aw, aw), "Skin")
        box(f"{side}ForeArm", (sx + s * (UARM + FARM / 2), 0, SHOULDER_Z), (FARM, aw * 0.85, aw * 0.85), "Skin")
        box(f"{side}Hand", (sx + s * (UARM + FARM + HAND * 0.4), 0, SHOULDER_Z), (HAND * 0.8, aw * 0.95, aw * 0.5), "Skin")
        # legs
        lx = s * LEGX
        box(f"{side}UpLeg", (lx, 0, HIP - THIGH * 0.3), (TW * 1.2, THIGH * 0.6, TW * 1.15), "Shorts")
        box(f"{side}UpLeg", (lx, 0, HIP - THIGH * 0.78), (TW * 0.95, THIGH * 0.45, TW * 0.95), "Skin")
        box(f"{side}Leg", (lx, 0, HIP - THIGH - SHIN * 0.31), (TW * 0.82, SHIN * 0.62, TW * 0.82), "Skin")
        box(f"{side}Leg", (lx, 0, HIP - THIGH - SHIN * 0.8), (TW * 0.86, SHIN * 0.4, TW * 0.86), "Sock")
        box(f"{side}Foot", (lx, -0.028 * H, FOOT / 2), (TW * 1.02, FOOT, 0.14 * H), "Shoe")

    me = bpy.data.meshes.new("PlayerBody")
    me.from_pydata(verts, [], faces)
    for m in mats.values():
        me.materials.append(m)
    for poly, mi in zip(me.polygons, face_mats):
        poly.material_index = mi
    me.update()
    body = bpy.data.objects.new("PlayerBody", me)
    bpy.context.scene.collection.objects.link(body)
    for bname, idx in groups.items():
        vg = body.vertex_groups.new(name=bname)
        vg.add(idx, 1.0, "REPLACE")
    body.parent = arm
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return body


# ------------------------------------------------------------- keyed posing
# Rotations are given in armature axes relative to the parent's posed frame,
# like the game's nested THREE.Groups. Axes (character faces -Y):
#   X = character's left.  Rx(+) tips an up-pointing bone forward and swings a
#   down-pointing bone backward.  Z = up (yaw).
# Arms: (spread, fwd, elbow):  spread 90 = hanging at the side, fwd swings the
# hanging arm forward (180 = straight overhead), elbow bends the forearm further
# the same way, so the forearm's angle is fwd + elbow (fwd 100 + elbow 80 puts
# the forearm straight up, the jump-shot set point).

def arm_q(s, spread, fwd, twist=0.0):
    return Euler((math.radians(-fwd), math.radians(s * spread), math.radians(s * twist)), "YXZ").to_quaternion()


def side_sign(name):
    return 1 if name.startswith("Left") else -1


def pose_to_rot(name, v):
    s = side_sign(name)
    if name.endswith("Arm") and not name.endswith("ForeArm"):
        return arm_q(s, *v)
    if name.endswith("ForeArm"):          # elbow flex (+ = bend)
        return Euler((0, 0, math.radians(-s * v)), "XYZ").to_quaternion()
    if name.endswith("Hand"):             # (flex, cock): flex + = palm-side curl
        flex, cock = v if isinstance(v, tuple) else (v, 0)
        return Euler((0, math.radians(s * cock), math.radians(-s * flex)), "XYZ").to_quaternion()
    if name.endswith("UpLeg"):            # (fwd, out)
        fwd, out = v if isinstance(v, tuple) else (v, 0)
        return Euler((math.radians(-fwd), math.radians(-s * out), 0), "XYZ").to_quaternion()
    if name.endswith("Leg"):              # knee bend
        return Euler((math.radians(v), 0, 0), "XYZ").to_quaternion()
    if name.endswith("Foot"):             # + = toes down
        return Euler((math.radians(v), 0, 0), "XYZ").to_quaternion()
    # spine/neck/head/hips: (lean fwd, side tilt, yaw)
    x, y, z = v if isinstance(v, tuple) else (v, 0, 0)
    return Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ").to_quaternion()


def apply_pose(arm, pose):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    for name, v in pose.items():
        if name == "loc":
            continue
        pb = arm.pose.bones[name]
        rest = pb.bone.matrix_local.to_quaternion()
        pb.rotation_quaternion = rest.inverted() @ pose_to_rot(name, v) @ rest
    if "loc" in pose:  # Hips offset in armature axes (x, y, z) metres
        pb = arm.pose.bones["Hips"]
        pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(pose["loc"])


def key_all(arm, frame):
    for pb in arm.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
        if pb.name == "Hips":
            pb.keyframe_insert("location", frame=frame)


def both(base, **over):
    p = dict(base)
    p.update(over)
    return p


def mirror(pose):
    """Swap Left/Right and flip sideways components."""
    out = {}
    for k, v in pose.items():
        if k == "loc":
            out[k] = (-v[0], v[1], v[2])
            continue
        nk = k.replace("Left", "@").replace("Right", "Left").replace("@", "Right")
        if k in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head"):
            x, y, z = v if isinstance(v, tuple) else (v, 0, 0)
            v = (x, -y, -z)
        out[nk] = v
    return out


STANCE = {
    "loc": (0, 0, -0.06),
    "Hips": (6, 0, 0), "Spine": (6, 0, 0), "Spine1": (4, 0, 0), "Neck": (-8, 0, 0), "Head": (-4, 0, 0),
    "LeftUpLeg": (28, 6), "RightUpLeg": (28, 6), "LeftLeg": 40, "RightLeg": 40,
    "LeftFoot": -14, "RightFoot": -14,
    "LeftArm": (78, 18), "RightArm": (78, 18), "LeftForeArm": 30, "RightForeArm": 30,
}


def clip(arm, name, keys):
    """keys: list of (frame, pose). Looping clips repeat their first pose last."""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    for f, pose in keys:
        apply_pose(arm, pose)
        key_all(arm, f)
    return act


def keyed_clips(arm):
    acts = {}
    # Idle: athletic stance, breathing.
    acts["Idle"] = clip(arm, "Idle", [
        (1, STANCE),
        (31, both(STANCE, loc=(0, 0, -0.07), Spine1=(6, 0, 0), LeftArm=(80, 20), RightArm=(80, 20))),
        (61, STANCE),
    ])

    # Run: 20-frame stride (two steps).
    def run_pose(p):  # p = +1 left leg forward
        return {
            "loc": (0, 0, -0.03), "Hips": (10, 0, -6 * p), "Spine": (6, 0, 4 * p), "Spine1": (2, 0, 4 * p), "Neck": (-10, 0, 0),
            "LeftUpLeg": 38 * p - 8, "RightUpLeg": -38 * p - 8,
            "LeftLeg": 30 if p > 0 else 85, "RightLeg": 85 if p > 0 else 30,
            "LeftFoot": -10 if p > 0 else 20, "RightFoot": 20 if p > 0 else -10,
            "LeftArm": (82, -40 * p), "RightArm": (82, 40 * p), "LeftForeArm": 85, "RightForeArm": 85,
        }

    def run_pass(p):
        q = run_pose(p)
        q.update({"loc": (0, 0, 0.02), "LeftUpLeg": 10 if p > 0 else -20, "RightUpLeg": -20 if p > 0 else 10,
                  "LeftLeg": 20 if p > 0 else 100, "RightLeg": 100 if p > 0 else 20,
                  "LeftArm": (82, -10 * p), "RightArm": (82, 10 * p)})
        return q
    acts["Run"] = clip(arm, "Run", [(1, run_pose(1)), (6, run_pass(-1)), (11, run_pose(-1)), (16, run_pass(1)), (21, run_pose(1))])

    # Dribble (right hand): ball goes down on 1-8, comes back up 8-16.
    low = both(STANCE, loc=(0, 0, -0.14), Hips=(14, 0, 8), Spine=(10, 0, 0), Spine1=(6, 0, 0), Neck=(-18, 0, 0),
               LeftUpLeg=(45, 8), RightUpLeg=(32, 8), LeftLeg=70, RightLeg=60, LeftFoot=-25, RightFoot=-20,
               LeftArm=(70, 55, 20), LeftForeArm=70, LeftHand=(10, 0))
    drib_up = both(low, RightArm=(82, 40), RightForeArm=75, RightHand=(-35, 0))
    drib_dn = both(low, loc=(0, 0, -0.16), RightArm=(84, 22), RightForeArm=20, RightHand=(30, 0))
    acts["Dribble"] = clip(arm, "Dribble", [(1, drib_up), (6, drib_dn), (9, drib_dn), (16, drib_up)])

    # Crossover: right hand pushes ball across, body jab-steps right then shifts left.
    left_drib = mirror(drib_up)
    jab = both(drib_up, loc=(-0.10, 0, -0.18), Hips=(16, -6, -18), Spine=(10, -6, -6),
               RightUpLeg=(55, 20), RightLeg=80, LeftUpLeg=(20, 0), LeftLeg=50)
    push = both(jab, loc=(0.0, 0, -0.2), Hips=(16, 0, 0), Spine=(12, 0, 0),
                RightArm=(85, 35, 0), RightForeArm=45, RightHand=(35, 25),
                LeftArm=(80, 30), LeftForeArm=60, LeftHand=(-20, 0))
    catch = both(mirror(jab), LeftArm=(84, 25), LeftForeArm=30, LeftHand=(25, 0))
    acts["Crossover"] = clip(arm, "Crossover", [
        (1, drib_up), (7, jab), (12, push), (18, catch), (26, left_drib)])

    # Jumper: dip, set, rise, release at 21, follow-through, land.
    hold = both(STANCE, RightArm=(80, 35, -10), RightForeArm=95, RightHand=(-30, 0),
                LeftArm=(70, 30, 20), LeftForeArm=95, LeftHand=(-10, 0))
    dip = both(hold, loc=(0, 0, -0.2), Hips=(18, 0, 0), Spine=(10, 0, 0), LeftUpLeg=(55, 6), RightUpLeg=(55, 6),
               LeftLeg=95, RightLeg=95, LeftFoot=-35, RightFoot=-35, Neck=(-20, 0, 0))
    set_ = both(STANCE, loc=(0, 0, 0.05), Hips=(0, 0, 0), Spine=(-2, 0, 0), Spine1=(0, 0, 0), Neck=(-6, 0, 0),
                LeftUpLeg=(4, 3), RightUpLeg=(4, 3), LeftLeg=6, RightLeg=6, LeftFoot=25, RightFoot=25,
                RightArm=(84, 105, -10), RightForeArm=75, RightHand=(-55, 0),
                LeftArm=(68, 95, 25), LeftForeArm=80, LeftHand=(-15, 0))
    peak = both(set_, loc=(0, 0, 0.55), LeftFoot=35, RightFoot=35, LeftLeg=14, RightLeg=10, LeftUpLeg=(10, 3))
    peak["RightArm"], peak["RightForeArm"] = (84, 125, -10), 55
    release = both(peak, loc=(0, 0, 0.6), RightArm=(86, 160, -10), RightForeArm=5, RightHand=(75, 0),
                   LeftArm=(66, 115, 25), LeftForeArm=55)
    fall = both(release, loc=(0, 0, 0.25), LeftLeg=25, RightLeg=25, LeftFoot=20, RightFoot=20)
    land = both(STANCE, loc=(0, 0, -0.12), LeftLeg=55, RightLeg=55, LeftUpLeg=(38, 6), RightUpLeg=(38, 6),
                RightArm=(84, 145, -10), RightForeArm=10, RightHand=(70, 0), LeftArm=(72, 100), LeftForeArm=40)
    acts["Jumper"] = clip(arm, "Jumper", [
        (1, STANCE), (7, dip), (13, set_), (18, peak), (21, release), (27, fall), (31, land), (38, land),
        (46, STANCE)])

    # Dunk: gather, load, explode, cock the ball back, slam, hang on rim, drop, land.
    gather = both(STANCE, loc=(0, 0, -0.1), Hips=(14, 0, 10), Spine=(12, 0, 0),
                  LeftUpLeg=(50, 4), RightUpLeg=(-5, 4), LeftLeg=50, RightLeg=40,
                  RightArm=(78, 40, -15), RightForeArm=95, LeftArm=(75, 38, 15), LeftForeArm=95)
    load = both(gather, loc=(0, 0, -0.28), Hips=(24, 0, 0), Spine=(14, 0, 0), Neck=(-28, 0, 0),
                LeftUpLeg=(70, 6), RightUpLeg=(68, 6), LeftLeg=110, RightLeg=110, LeftFoot=-40, RightFoot=-40,
                RightArm=(80, -20, -10), LeftArm=(80, -20, 10), RightForeArm=40, LeftForeArm=40)
    up = both(STANCE, loc=(0, 0, 0.6), Hips=(-6, 0, 0), Spine=(-6, 0, 0), Spine1=(-4, 0, 0), Neck=(-10, 0, 0),
              LeftUpLeg=(45, 4), RightUpLeg=(-10, 4), LeftLeg=80, RightLeg=15, LeftFoot=35, RightFoot=40,
              RightArm=(85, 155), RightForeArm=15, LeftArm=(80, 150), LeftForeArm=15)
    cock = both(up, loc=(0, 0, 1.0), Spine=(-14, 0, 0), Spine1=(-8, 0, 0),
                LeftUpLeg=(55, 8), RightUpLeg=(20, 8), LeftLeg=95, RightLeg=70,
                RightArm=(86, 180), RightForeArm=70, RightHand=(-40, 0),
                LeftArm=(80, 165), LeftForeArm=10)
    slam = both(cock, loc=(0, 0, 0.98), Spine=(16, 0, 0), Spine1=(10, 0, 0), Neck=(-20, 0, 0),
                RightArm=(86, 140), RightForeArm=5, RightHand=(60, 0), LeftArm=(80, 120), LeftForeArm=30,
                LeftUpLeg=(40, 10), RightUpLeg=(40, 10), LeftLeg=80, RightLeg=80)
    hang = both(slam, loc=(0, 0, 0.92), Spine=(4, 0, 0), Spine1=(0, 0, 0), Neck=(-6, 0, 0),
                RightArm=(86, 172), RightForeArm=10, RightHand=(20, 0), LeftArm=(80, 175), LeftForeArm=10,
                LeftUpLeg=(25, 10), RightUpLeg=(30, 10), LeftLeg=70, RightLeg=75, LeftFoot=30, RightFoot=30)
    drop = both(hang, loc=(0, 0, 0.35), LeftUpLeg=(15, 6), RightUpLeg=(15, 6), LeftLeg=20, RightLeg=20,
                RightArm=(80, 90), RightForeArm=40, LeftArm=(80, 90), LeftForeArm=40, LeftFoot=10, RightFoot=10)
    land = both(STANCE, loc=(0, 0, -0.2), Hips=(18, 0, 0), Spine=(10, 0, 0),
                LeftUpLeg=(55, 8), RightUpLeg=(55, 8), LeftLeg=90, RightLeg=90, LeftFoot=-30, RightFoot=-30,
                LeftArm=(60, 30), RightArm=(60, 30), LeftForeArm=60, RightForeArm=60)
    acts["Dunk"] = clip(arm, "Dunk", [
        (1, STANCE), (7, gather), (13, load), (19, up), (24, cock), (28, slam), (36, hang), (44, hang),
        (50, drop), (55, land), (66, STANCE)])
    return acts


def mixamo_clips(arm):
    if not os.path.isdir(MIXAMO_DIR):
        return []
    done = []
    for fn in sorted(os.listdir(MIXAMO_DIR)):
        if fn.lower().endswith(".fbx"):
            name = os.path.splitext(fn)[0]
            old = bpy.data.actions.get(name)
            if old:
                bpy.data.actions.remove(old)
            retarget_fbx(arm, os.path.join(MIXAMO_DIR, fn), name)
            done.append(name)
    return done


def export(arm, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    apply_pose(arm, {})
    arm.animation_data.action = None
    bpy.context.scene.frame_set(1)
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", export_animation_mode="ACTIONS",
        export_force_sampling=True, export_frame_step=1, export_optimize_animation_size=True,
        export_skins=True, export_yup=True, export_cameras=False, export_lights=False,
        export_def_bones=False)


def main():
    reset_scene()
    arm = make_armature()
    body = make_body(arm, make_materials())
    keyed_clips(arm)
    retargeted = mixamo_clips(arm)
    export(arm, OUT)
    print(f"Wrote {OUT} ({os.path.getsize(OUT) // 1024} KB); "
          f"{len(body.data.polygons)} faces; clips: {', '.join(sorted(a.name for a in bpy.data.actions))}; "
          f"from Mixamo: {', '.join(retargeted) or 'none'}")


if __name__ == "__main__":
    main()
