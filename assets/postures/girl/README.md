# The girl's posture pictures

**Complete.** All ten are here, built from the drawings with
`python3 tools/build_postures.py <folder> assets/postures/girl`.

The qunut is the same pose as the standing folded one, so the two pictures are the same
drawing, as they are in the boy's set (his `qunut.png` is a second drawing of the folded
stance). Replace `qunut.png` here if you would rather she were drawn differently for it.


**Her poses still need checking.** They follow the boy's, pose for pose. In the Hanafi school a
woman's ruku, sujood and sitting are not the same as a man's, so someone qualified should go over
these before anyone learns from them.

Drop pictures in here with **exactly these names** and the app offers "Girl" in Settings, under
**Who is shown**. Anything missing falls back to the boy's picture of the same name, so the set
can be filled in a few at a time.

| File | The posture |
|---|---|
| `standing_arms_down.png` | standing straight, arms at the sides (the intention screen) |
| `takbir_raised.png` | hands raised to the ears for the takbir |
| `standing_folded.png` | standing with the hands folded |
| `ruku.png` | bowing, hands on the knees (side view) |
| `standing_itidal.png` | standing straight again after bowing, arms at the sides (side view) |
| `sujood.png` | prostrating (side view) |
| `jalsa.png` | sitting between the two prostrations |
| `tashahhud.png` | sitting for the tashahhud |
| `salam.png` | turning the head right and left for the salam (both in one picture) |
| `qunut.png` | standing with the hands folded, for the qunut of witr |

Match the boy's set: black line art on white, no grey, no colour, no lettering and no watermark;
the same prayer mat; the figure standing on the bottom edge of the picture; a plain white
background with a little clear space around the figure. Trim each picture so the figure fills
it, as the app scales each one to the frame.

`modes.json` here is optional. It says how tall each posture is against a standing figure, so a
bowing figure is not blown up to full height:

```json
{ "ruku": 0.68, "sujood": 0.42, "jalsa": 0.60, "tashahhud": 0.62, "salam": 0.60 }
```

Leave it out and the boy's numbers are used, which is usually close enough. To work them out
from the pictures themselves: `python3 tools/build_postures.py` (see that file).
