# The drawing the unit-screen arch is built from

`arch.png` is the arch as a solid shape, kept here so the masks can be rebuilt at any time:

    python3 tools/build_arch.py assets/mosque/source/arch.png

That writes `arch-outer.png` and `arch-inner.png` in the folder above. Replace `arch.png` with a
new drawing and run it again to change the arch's shape. Any colour on a transparent or white
background will do; it is only the shape that is read.
