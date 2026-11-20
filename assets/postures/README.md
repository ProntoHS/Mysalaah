# The posture pictures

Ten per figure, named for the posture the app asks for. The boy's set is this folder; every
other figure has a folder of its own beside it, and `girl/README.md` says what a new set has to
look like. `modes.json` says how tall each posture is drawn against a standing figure.

## The coloured twins

Beside each picture is a `<posture>-colour.png`, shown only in the colour theme. Nothing is
replaced: the light and dark mats go on using the line drawings they have always used, and a
mat that never selects colour cannot tell these exist.

Harry painted them and sent them on 19 November 2026 — "i have included coloured prayer step
pictures for both girl & boy, this should be used in coloured theme, the dimensions should be
the same" — and `tools/postures/install_colour.py` put them in.

**The dimensions were not the same as they arrived**, and making them the same is not just a
matter of the canvas. `render.PostureView` scales a picture into its frame and stands it on the
bottom line, and `modes.json` is written against the pictures that ship. So what has to agree
is where the DRAWING sits inside the canvas, not merely how big the file is: get that wrong and
the child changes size, or hops up the screen, at the moment the theme changes — which is the
one moment a child is watching the picture rather than the words. Each twin is therefore built
to its original's exact canvas with the drawing scaled, undistorted, into the exact rectangle
the original's drawing occupies. Cropped to the ink, eight of the ten already agreed with the
mat to within a tenth of a per cent, which is how we know he drew each one over the mat's own
picture.

They keep the black ground he drew on rather than having it cut away. The colour theme sits on
black by definition, so an opaque black ground is invisible under the drawing, and deciding
which blacks in a picture are background and which are the outlines of the child, the prayer
mat and the lines on it is a judgement that went wrong once already, on the wu'du steps at 2.44.

Deleting a `-colour.png` is safe at any time: that step falls back to the line drawing, in every
theme, and only that step.

### Which of his pictures became which posture

Eighteen of the twenty were settled by looking and then confirmed by measurement — cropped to
the drawing, each of his agrees with the mat's shape to within 0.7%, and most to within a tenth
of a per cent.

**The two folded ones needed asking**, because qunut and standing folded are the same stance
differing only in where the hands sit. Harry's answer, on 19 November 2026, was "07 and 16 are
qunut". The measurement agrees with him on the girl and not on the boy:

| | his picture | what it measures as | how far off |
|---|---|---|---|
| girl | `16_qiyam_girl_folded_alt` | qunut | 0.66% — **as he said** |
| girl | `13_qiyam_girl_folded` | standing folded | 0.36% |
| boy | `03_qiyam_boy_folded` | qunut | 0.05% |
| boy | `07_qiyam_boy_folded_alignment` | standing folded | 0.28% — **the other way round** |

against a worst case of 0.7% across the eighteen not in doubt. The boy's pair is therefore
installed the way it measures rather than the way it was answered, and Harry has been told
exactly that. Two lines in `tools/postures/install_colour.py` to swap back if he says otherwise.

### Still unchecked

The same caveat as everywhere else in this folder, and it has not moved: **nobody qualified has
looked at any of this.** The girl's poses follow the boy's, pose for pose, and in the Hanafi
school a woman's ruku, sujood and sitting are not the same as a man's — see `girl/README.md`.
Harry's coloured drawings follow the same poses, so they inherit the same open question, and
colouring them in has not answered it.

What they do hold to: no faces. Hijab, hands and feet, and nothing inside the outline of the
face, in both sets — which is the rule the line drawings are held to and was checked on his.
