# Overnight quality pass

**Summary:** 13 rounds, 10 improvements shipped (AI offense, help defense, pick and roll, 1v1 big-man play, dunk cam, celebrations, floodlights, ambience, sneaker squeaks, phone layout fix). Every shipped change passed: all 8 dunk types 4/4, AI sims in every mode with no errors, the online two-player mock, and the VIP build code. Stopped when the remaining ideas either couldn't be verified headlessly (online smoothing) or were too small to be worth the risk.

**Ideas for next time (need a real person playing):** online movement smoothing on the guest's screen tested on two real devices; camera distance (closer like 2K?) — a taste call for you; AI jump-shot accuracy (~30%) is by design of the green-or-miss system, but could be tuned if AI teammates feel too bricky.

Each entry: what I found by playing/simulating, what I changed, and how it tested.

## 1. AI offense was mostly bad jump shots
- **Found:** over 6 simulated AI games, 85% of AI shots were jumpers and only 25% went in (33% FG overall). Many were forced at the end of the shot clock after the AI wandered around the perimeter.
- **Changed:** the AI ball handler now
  - only settles for a jumper when it is genuinely open (or the green chance is high when guarded),
  - attacks the rim more often, especially when a defender is crowding it,
  - starts a drive when the shot clock gets under 5 or it has held the ball too long, instead of running the clock out,
  - kicks it out to an open teammate when its drive gets cut off.
- **Result:** 48% FG, jumpers down to 70% of shots, more dunks, layups and floaters. Games finish faster.
- **Tests:** all 8 dunk types 4/4, all modes sim clean, online mock OK, VIP code OK.

## 2. No help defense, and AI never missed at the rim
- **Found:** stress tests (stuck balls, out of bounds, frozen states) came back clean. But AI defenders only ever guarded their own man, so once a driver beat his defender nobody stepped in. And AI layups, floaters and euros went in 100% of the time, so there was no way to stop an AI drive.
- **Changed:**
  - The off-ball defender now sprints into the lane with arms up when the ball handler beats his man inside about 17 feet, then recovers when the ball moves. This also leaves a shooter open for a kick-out, like real help defense.
  - AI finishing timing is less perfect, so contested AI layups can now miss. Open ones still go in almost every time.
  - Your own meters and green windows are unchanged.
- **Result:** AI finishes around 85% instead of 100%; more posters and contested dunks for you when you drive into help.
- **Tests:** dunks 8/8 types 4/4, all modes clean, online mock OK, VIP code OK.

## 3. The court was dead silent between plays
- **Found:** outside of bounces, rims and swishes there was no background sound at all, so the night court felt empty.
- **Changed:** added a quiet ambience bed once sound starts: a low distant-city rumble plus a faint, slowly breathing crowd/street murmur. It sits well under every gameplay sound and the Sound: off button mutes it.
- **Tests:** ambience loops start (verified), dunks 4/4 all types, all modes clean, online mock OK.

## 4. Flat lighting on the court
- **Found:** measured movement response (about 0.25 s to full speed, reverse or stop) and dead time between possessions (about 3 s) — both fine. Visually, though, the court was lit perfectly evenly even though there are two big floodlight poles, so it looked flat.
- **Changed:** added warm light pools on the court under each floodlight and a glow on the lamp heads. Done with cheap textured overlays, so no extra lights or shadow cost on phones.
- **Tests:** screenshots checked, dunks 4/4 all types, all modes clean, online mock OK.

## 5. Pick and roll
- **Found:** checked draw calls (about 230, fine for phones), the end-of-game screen, and close-up animation frames; nothing broken. The biggest thing missing compared with 2K/streetball was that teammates never set screens — offense was just one guy dribbling.
- **Changed:** an AI teammate now sometimes runs up and sets a screen on the ball handler's defender (beside him, on the side toward the middle), plants and holds it for about a second (hard to push through), then rolls to the rim for a pass. When an AI handler gets the screen it attacks off it. Your AI teammate will set screens for you too.
- **Result:** about a dozen screens a game; defenders get hung up and the handler comes off free.
- **Tests:** screenshots of a screen checked, dunks 4/4 all types, all modes clean, online mock OK, VIP code OK.

## 6. Dunk cam
- **Found:** the camera stayed at its normal distance through your dunks, so even the ferocious ones read small on screen.
- **Changed:** when you (single local player) go up for a dunk, the camera smoothly pushes in about 30% closer and tilts up toward the rim, holds through the slam and hang, then eases back out. Skipped if your device has reduced motion turned on. Two-player same-screen modes keep the normal camera so neither player loses the view.
- **Tests:** frame strip of a double clutch checked, dunks 4/4 all types, all modes clean, online mock OK.

## 7. Sneaker squeaks on hard cuts
- **Found:** shoes only squeaked during dribble moves; sharp cuts, closeouts and hard stops were silent, which made movement feel floaty compared with a real court.
- **Changed:** any player on the floor who cuts hard (big direction change at speed) or plants from a sprint now squeaks, with a little pitch variation so it doesn't sound repetitive. Yours are louder than the AI's. Rate-limited per player.
- **Result:** about one squeak every two seconds across all four players in a 2v2.
- **Tests:** dunks 4/4 all types, all modes clean, online mock OK.

## 8. Big men in 1v1 just shot jumpers
- **Found:** in 1v1 (to 11), Tank (6'10", 93 strength) took almost all jumpers against a smaller guard and went 32% on them, losing most games. He never used his size, because the AI only drove when the lane was empty — and in 1v1 the defender is always in the lane.
- **Changed:** in 1v1 only, an AI handler who is clearly stronger/heavier than his defender will sometimes put his shoulder down and power-drive from inside about 20 feet, bulling through contact instead of giving up when the lane is closed. 2v2 is unchanged (help defense handles drives there).
- **Result:** Tank now plays like a big: jumpers dropped from 79% of his shots to about 40%, more dunks, layups and floaters, and 1v1 games are much more competitive.
- **Tests:** dunks 4/4 all types, all modes clean, online mock OK.

## 9. Every make got the same celebration
- **Found:** every made basket ended with the same two hops and arms overhead, whether it was a layup or a poster dunk.
- **Changed:**
  - After a dunk: a crouched, fists-up flex/roar with the chest pumping.
  - After a made three: the shooter holds his follow-through (arm up, wrist snapped) and backpedals.
  - Other makes keep the hop.
  - Online guests see the same celebration as the host.
- **Tests:** close-up screenshots of each pose, dunks 4/4 all types, all modes clean, online mock OK.

## 10. Phone portrait: Sound/Pause buttons sat on top of SPIN/PASS
- **Found:** also checked memory over 12 back-to-back games (no leak). Then emulated phones: on a portrait phone (iPhone 13, SE, Pixel 5) the Sound and Pause buttons were placed just above the action buttons and overlapped SPIN and PASS, so a thumb could pause or mute the game mid-play.
- **Changed:** on narrow screens the two buttons now sit small in the top-right just under the scoreboard, and the shot feedback card moved down a touch so they never collide.
- **Tests:** checked every visible button rectangle for overlaps on three phone sizes (none), screenshot checked, all modes clean, online mock OK.

## (Round 11–12: investigated, nothing shipped)
- Thought the AI teammate was a ball hog; a better measurement showed it shares normally. No change.
- Tried smoothing other players' movement and jumps on the online guest's screen. My headless two-window test can't reproduce real network timing well enough to prove it helps (one version measured jerkier), so I left online play as it was rather than risk making it worse. Worth a real two-device test later.
