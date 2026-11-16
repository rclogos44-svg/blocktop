# Blender player pipeline

Builds the blocky, rigged Blocktop player and exports `assets/player.glb` for three.js.

```
pip install bpy==5.2.4          # Blender as a Python module (Python 3.13), or use Blender 5.x itself
python blender/build_player.py  # or: blender -b -P blender/build_player.py
python blender/test_retarget.py # checks the Mixamo retargeter
```

Preview the result in `player-viewer.html` (live at https://rclogos44-svg.github.io/blocktop/player-viewer.html once pushed to the Pages branch). Add `?clip=Dunk` to open a specific clip.

## What's in the .glb

- **Rig:** Mixamo bone names (`Hips`, `Spine`, `Spine1`, `Spine2`, `Neck`, `Head`, `Left/RightShoulder`, `Arm`, `ForeArm`, `Hand`, `UpLeg`, `Leg`, `Foot`, `ToeBase`), resting in a T-pose. The character faces +Z in three.js and stands 6'6" (1.98 m) tall.
- **Body:** 31 boxes (186 faces), each weighted 100% to one bone, with the same proportions as `Player.computeDims()` in `index.html`. Materials are named `Skin`, `Jersey`, `Shorts`, `Trim`, `Sock`, `Shoe` and `Eyes`, so you can recolor by name per team (the viewer shows how).
- **Clips (30 fps, in place):** `Idle` and `Run` loop, plus `Dribble` (loops), `Crossover`, `Jumper` and `Dunk`. The game moves the player; the clips only move the body. The `Hips` bone still rises and falls for jumps (the jumper peaks about 0.6 m up, the dunk about 1.0 m).

## Mixamo clips

Mixamo needs a logged-in Adobe account, so download the clips yourself and put them in `blender/mixamo/` (see the README there). The retargeter (`retarget_mixamo.py`) copies each bone's rotation relative to its rest pose, so bone rolls and scale don't have to match Mixamo's. The one requirement is that both rigs rest in a T-pose, which Mixamo's do. Finger bones are ignored, and the hip height is scaled to the player's size.

## Tuning the keyed clips

The poses live in `keyed_clips()` in `build_player.py`. Angles are in degrees, in the parent's frame:

- **Arms:** `(spread, fwd, twist)`. `spread` 90 hangs the arm at the side. `fwd` swings it forward: 90 is level in front, 180 is straight overhead.
- **Elbow:** adds to `fwd`. For example, `fwd` 100 plus elbow 80 puts the forearm straight up, which is the jump-shot set point.
- **Legs:** `UpLeg` takes `(fwd, out)`, `Leg` is the knee bend, and `Foot` is positive when the toes point down.
- **Spine, neck and head:** `(lean forward, side tilt, yaw)`.
- **`loc`:** the hip offset in metres as `(x, y, z)`.

## Not wired into the game yet

`index.html` still draws its own procedural box player. To switch the game over, load `assets/player.glb` with `THREE.GLTFLoader`, give each player a `SkeletonUtils.clone` of it plus an `AnimationMixer`, and pick a clip from the player's state (`dribble`, `cross`, `shoot`, `dunk` and so on).
