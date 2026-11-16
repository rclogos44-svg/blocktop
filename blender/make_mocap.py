"""Turn CMU motion capture into animation data the game's own rig can play.

    python blender/make_mocap.py        (needs `pip install bpy`, or run inside Blender)

Downloads a few takes from the free CMU Graphics Lab Motion Capture Database
(mocap.cs.cmu.edu, BVH conversion by B. Hahne; free for any use), retargets
them onto the player rig (retarget_mixamo.py) and writes assets/mocap.js:
per-frame quaternions for each of the game's joint groups (pelvis, spine,
chest, neck, head, hips/knees/ankles, shoulders/elbows/wrists), in three.js
axes, relative to the game's rest pose (arms hanging), plus the pelvis height.

Clips:
  run      one stride cycle, synced in game to the leg phase
  dribwalk one low dribbling-walk cycle (legs/torso; the dribbling arm stays
           with the game's ball code)
  dribble  a standing dribble loop
  jumper   a real jump shot, with takeoff and release marked so the game can
           time-warp it to its own jump and release
"""
import json
import math
import os
import sys
import urllib.request

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_player as B  # noqa: E402
from retarget_mixamo import retarget  # noqa: E402

CACHE = os.path.join(HERE, "cmu")
OUT = os.path.join(REPO, "assets", "mocap.js")
MIRROR = "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data"
SRC_FPS, FPS = 120, 60
STEP = SRC_FPS // FPS

# game joint -> rig bone whose orientation drives it, and the game parent joint
JOINTS = [
    ("pelvis", "Hips", None), ("spine", "Spine", "pelvis"), ("chest", "Spine2", "spine"),
    ("neck", "Neck", "chest"), ("head", "Head", "neck"),
    ("hipL", "LeftUpLeg", "pelvis"), ("kneeL", "LeftLeg", "hipL"), ("ankL", "LeftFoot", "kneeL"),
    ("hipR", "RightUpLeg", "pelvis"), ("kneeR", "RightLeg", "hipR"), ("ankR", "RightFoot", "kneeR"),
    ("shL", "LeftArm", "chest"), ("elL", "LeftForeArm", "shL"), ("wrL", "LeftHand", "elL"),
    ("shR", "RightArm", "chest"), ("elR", "RightForeArm", "shR"), ("wrR", "RightHand", "elR"),
]

# (name, take, first frame, last frame @120fps, kind)
CLIPS = [
    ("run", "09_01", 13, 149, "cycle"),
    ("dribwalk", "06_09", 13, 302, "cycle"),
    ("dribble", "06_15", 40, 230, "cycle"),
    ("jumper", "06_15", 200, 480, "once"),
]


def fetch(take):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, take + ".bvh")
    if not os.path.exists(path):
        subj = take.split("_")[0].zfill(3)
        url = f"{MIRROR}/{subj}/{take}.bvh"
        print("downloading", url)
        urllib.request.urlretrieve(url, path)
    return path


def world_rot(arm, bone):
    return (arm.matrix_world @ arm.pose.bones[bone].matrix).to_3x3().normalized().to_quaternion()


def game_rest(arm):
    """World rotation of each bone in the game's rest pose (arms hanging)."""
    B.apply_pose(arm, {"LeftArm": (90, 0), "RightArm": (90, 0)})
    bpy.context.view_layer.update()
    rest = {b: world_rot(arm, b) for _, b, _ in JOINTS}
    B.apply_pose(arm, {})
    return rest


def to_three(q):
    # Blender (x, y, z) -> three (x, z, -y): a proper rotation, so the
    # quaternion's vector part maps the same way.
    return (q.x, q.z, -q.y, q.w)


def sample(arm, rest, f0, f1):
    """Per output frame: world deltas per joint, hip height, foot/hand positions."""
    sc = bpy.context.scene
    frames = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        D = {j: world_rot(arm, b) @ rest[b].inverted() for j, b, _ in JOINTS}
        P = arm.pose.bones
        pos = {n: (arm.matrix_world @ P[n].head).copy() for n in ("Hips", "LeftFoot", "RightFoot", "LeftHand", "RightHand")}
        frames.append({"D": D, "pos": pos})
    return frames


def forward(D_pelvis):
    v = D_pelvis @ Vector((0, -1, 0))  # character front is -Y in Blender
    return math.atan2(v.x, -v.y)        # yaw of the front, 0 = facing -Y


def encode(frames, yaw):
    """Local game quaternions (three axes) + pelvis height ratio, facing normalized."""
    fix = Quaternion((0, 0, 1), -yaw)
    qs, hs = [], []
    for fr in frames:
        D = {j: fix @ q for j, q in fr["D"].items()}
        row = []
        for j, _, parent in JOINTS:
            local = (D[parent].inverted() @ D[j]) if parent else D[j]
            if local.w < 0:
                local.negate()
            row.extend(round(v, 3) for v in to_three(local))
        qs.append(row)
        hs.append(round(fr["pos"]["Hips"].z / B.HIP, 4))
    return qs, hs


def qdist(a, b):
    s = 0.0
    for i in range(0, len(a), 4):
        d = abs(sum(a[i + k] * b[i + k] for k in range(4)))
        s += 1 - min(1.0, d)
    return s


def find_cycle(qs, pmin, pmax):
    best = None
    n = len(qs)
    for P in range(pmin, min(pmax, n - 1) + 1):
        for s in range(0, n - P):
            c = qdist(qs[s], qs[s + P]) + 0.5 * qdist(qs[min(n - 1, s + 3)], qs[min(n - 1, s + P + 3)])
            if best is None or c < best[0]:
                best = (c, s, P)
    return best


def slerp_row(a, b, t):
    out = []
    for i in range(0, len(a), 4):
        qa = Quaternion((a[i + 3], a[i], a[i + 1], a[i + 2]))
        qb = Quaternion((b[i + 3], b[i], b[i + 1], b[i + 2]))
        q = qa.slerp(qb, t)
        out.extend(round(v, 4) for v in (q.x, q.y, q.z, q.w))
    return out


def make_cycle(frames, qs, hs, pmin, pmax):
    cost, s, P = find_cycle(qs, pmin, pmax)
    cq, ch = qs[s:s + P], hs[s:s + P]
    # Seam: ease the last third toward the frames that follow the cycle start.
    k = max(2, P // 4)
    for i in range(k):
        t = (i + 1) / (k + 1)
        j = P - k + i
        cq[j] = slerp_row(qs[s + P - k + i], qs[s + i - k] if s + i - k >= 0 else qs[s], t * t)
    # Phase: start where the left foot is furthest forward of the hips.
    fwd_vals = []
    for f in frames[s:s + P]:
        yaw = forward(f["D"]["pelvis"])
        dirv = Vector((math.sin(yaw), -math.cos(yaw), 0))
        fwd_vals.append((f["pos"]["LeftFoot"] - f["pos"]["Hips"]).dot(dirv))
    z = max(range(P), key=lambda i: fwd_vals[i])
    cq, ch = cq[z:] + cq[:z], ch[z:] + ch[:z]
    return cq, ch, {"cost": round(cost, 3), "start": s, "period": P}


def build():
    B.reset_scene()
    arm = B.make_armature()
    rest = game_rest(arm)
    out = {"fps": FPS, "joints": [j for j, _, _ in JOINTS], "clips": {},
           "credit": "CMU Graphics Lab Motion Capture Database, mocap.cs.cmu.edu"}
    for name, take, f0, f1, kind in CLIPS:
        before = set(bpy.data.objects)
        bpy.ops.import_anim.bvh(filepath=fetch(take), frame_start=1, use_fps_scale=False, rotate_mode="NATIVE")
        src = next(o for o in bpy.data.objects if o not in before)
        # Every CMU take starts standing in a T-pose: its hip height is "standing".
        ref = retarget(src, arm, 1, 1, "ref", in_place=True)
        arm.animation_data.action = ref
        bpy.context.scene.frame_set(1)
        h0 = (arm.matrix_world @ arm.pose.bones["Hips"].head).z / B.HIP
        bpy.data.actions.remove(ref)
        act = retarget(src, arm, f0, f1, name, in_place=True, step=STEP)
        src_act = src.animation_data.action
        bpy.data.objects.remove(src, do_unlink=True)
        bpy.data.actions.remove(src_act)
        arm.animation_data.action = act
        n = (f1 - f0) // STEP + 1
        frames = sample(arm, rest, 1, n)
        info = {}
        if kind == "cycle":
            yaws = [forward(f["D"]["pelvis"]) for f in frames]
            yaw = math.atan2(sum(math.sin(y) for y in yaws), sum(math.cos(y) for y in yaws))
            qs, hs = encode(frames, yaw)
            P0 = {"run": (30, 60), "dribwalk": (40, 110), "dribble": (20, 60)}[name]
            qs, hs, info = make_cycle(frames, qs, hs, *P0)
            clip = {"loop": 1, "n": len(qs)}
        else:
            # Release = right wrist highest; takeoff = last frame before both feet leave the floor.
            hand = [f["pos"]["RightHand"].z for f in frames]
            rel = max(range(len(frames)), key=lambda i: hand[i])
            feet = [min(f["pos"]["LeftFoot"].z, f["pos"]["RightFoot"].z) for f in frames]
            floor = min(feet)
            to = rel
            while to > 0 and feet[to] > floor + 0.04:
                to -= 1
            land = rel
            while land < len(frames) - 1 and feet[land] > floor + 0.04:
                land += 1
            yaw = forward(frames[rel]["D"]["pelvis"])
            qs, hs = encode(frames, yaw)
            lo, hi = max(0, to - int(0.45 * FPS)), min(len(qs), land + int(0.5 * FPS))
            qs, hs = qs[lo:hi], hs[lo:hi]
            clip = {"loop": 0, "n": len(qs), "to": round((to - lo) / FPS, 3), "rel": round((rel - lo) / FPS, 3),
                    "land": round((land - lo) / FPS, 3)}
            info = {"takeoff": to, "release": rel, "land": land, "hand_hi": round(hand[rel] - floor, 2)}
        clip["q"] = [v for row in qs for v in row]
        clip["h"] = [round(h / h0, 3) for h in hs]
        out["clips"][name] = clip
        print(f"{name}: {take} {len(qs)} frames {info}")
        bpy.data.actions.remove(act)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("// Generated by blender/make_mocap.py from the CMU Graphics Lab Motion Capture Database\n"
                 "// (mocap.cs.cmu.edu). Do not edit by hand.\n")
        fh.write("window.MOCAP=" + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    build()
