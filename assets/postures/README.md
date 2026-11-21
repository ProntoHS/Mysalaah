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

**He replaced the whole set on 21 November 2026** with a repaint of the same twenty poses, in
black, teal and gold: "i want to replace the coloured prayer steps with this new set." Same
twenty filenames, same poses, different painting. The pictures here are that second set.

**The dimensions were not the same as they arrived**, and making them the same is not just a
matter of the canvas. `render.PostureView` scales a picture into its frame and stands it on the
bottom line, and `modes.json` is written against the pictures that ship. So what has to agree
is where the DRAWING sits inside the canvas, not merely how big the file is: get that wrong and
the child changes size, or hops up the screen, at the moment the theme changes — which is the
one moment a child is watching the picture rather than the words. Each twin is therefore built
to its original's exact canvas with the drawing scaled into exactly the rectangle the
original's drawing occupies.

**That scaling now fills the rectangle rather than fitting inside it**, and the change came
from the second set. The first was traced over the mat's own pictures and never disagreed with
them by more than 0.7%, so fitting-and-centring left margins of under a pixel. The repaint is
drawn rather than traced and disagrees by up to 4.1%, and fitting it put four of the twenty 13
to 24 pixels from where the mat expects the figure — past the 12px that
`test_the_drawing_sits_where_the_mat_expects_to_find_it` allows, and past it for a good reason.
Filling instead squashes the figure by up to 4.1% and puts it exactly where it belongs. Harry
was shown the two side by side at full size and chose the squash: it cannot be seen, and the
figure shifting on a theme change can. `SHAPE` in the install tool is now the bound on that
squash, at 5%, and a picture past it wants redrawing rather than stretching.

They keep the black ground he drew on rather than having it cut away. The colour theme sits on
black by definition, so an opaque black ground is invisible under the drawing, and deciding
which blacks in a picture are background and which are the outlines of the child, the prayer
mat and the lines on it is a judgement that went wrong once already, on the wu'du steps at 2.44.

Deleting a `-colour.png` is safe at any time: that step falls back to the line drawing, in every
theme, and only that step.

### Which of his pictures became which posture

Six of the twenty are settled decisively by shape alone — ruku, sujood, jalsa, salam, standing
itidal and tashahhud each sit 3% to 53% from their nearest rival. Takbir and arms-down are
settled by looking, since raised hands and hands at the sides are not subtle.

**The two folded ones needed asking**, because qunut and standing folded are the same stance
differing only in where the hands sit. Harry's answer, on 19 November 2026, was "07 and 16 are
qunut", and **both figures now follow it**.

They did not at first. On the November set the shapes were traced closely enough to act as a
fingerprint, and on that set the boy's pair measured the other way round — 03 was 0.05% from
qunut where 07 was 0.28% from standing folded — so the boy was installed against his answer and
he was told so.

**The repaint removed that reason.** Measured against the ten line drawings, its four
front-standing poses now sit within 1–2% of *each other*, so aspect ratio no longer tells them
apart and the measurement that overruled him says nothing at all. What remains is his answer,
and two things agreeing with it:

- the girl's half is confirmed independently — `girl/qunut` carries a dashed alignment line on
  the mat, and `16_qiyam_girl_folded_alt` is the one that has it;
- his naming runs the same way on both figures: plain `folded` for standing folded, the
  `alt`/`alignment` variant for qunut.

Asked again on 21 November, he said: "put 07 back as qunut". Both figures now match what he
said and each other.

**A crooked thing found on the way**, older than any of this and not fixed here: in the mat's
own *line* drawings the dashed alignment line sits on `standing_folded` for the boy and on
`qunut` for the girl. One of those two is wrong. Nobody qualified has looked at either.

### Still unchecked

The same caveat as everywhere else in this folder, and it has not moved: **nobody qualified has
looked at any of this.** The girl's poses follow the boy's, pose for pose, and in the Hanafi
school a woman's ruku, sujood and sitting are not the same as a man's — see `girl/README.md`.
Harry's coloured drawings follow the same poses, so they inherit the same open question, and
colouring them in has not answered it.

What they do hold to: no faces. Hijab, hands and feet, and nothing inside the outline of the
face, in both sets — which is the rule the line drawings are held to and was checked on his.
