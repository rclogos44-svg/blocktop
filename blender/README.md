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

## Motion capture in the game (`make_mocap.py`)

```
python blender/make_mocap.py    # writes assets/mocap.js
```

This downloads a few takes from the free [CMU Graphics Lab Motion Capture Database](http://mocap.cs.cmu.edu) (BVH conversion by Bruce Hahne; free for any use) into `blender/cmu/`, which git ignores. It retargets them onto the rig and converts them into rotations for the game's own joints (pelvis, spine, chest, neck, head, hips, knees, ankles, shoulders, elbows, wrists). `index.html` loads `assets/mocap.js` and blends it over the coded animation in `mocapLayer()`:

| Clip | Take | Used for | Timing |
|---|---|---|---|
| `run` | 09_01 | running without the ball, and fast dribbling | one stride cycle, synced to the game's leg phase |
| `dribwalk` | 06_09 | moving dribble, 0.3–2.6 m/s | cycle synced to the leg phase |
| `dribble` | 06_15 | standing dribble | loops in real time |
| `jumper` | 06_15 | normal and pull-up jump shots (not fades) | time-warped: dip ends at the game's takeoff, holds the set point until the player releases, then plays the real release and lands when the game lands |

What stays on the coded animation:
- **The dribbling arm.** The ball physics drive it, so ball and hand stay together.
- **The handler's head and neck, and half the torso lean.** That keeps a heads-up handler instead of the mocap player looking down at the ball.
- **Everything else:** crossovers and other moves, layups, dunks, defense, blocks and celebrations.

Set `settings.mocap = false` in the console to compare against the old animation. To use different takes, change `CLIPS` in `make_mocap.py` and rerun it. Each CMU take starts in a T-pose, which is used as the standing height.

The CMU data comes from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217.
