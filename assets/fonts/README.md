# Fonts

Arabic faces, all under the SIL Open Font License 1.1 (see the OFL files here), so they can be
shipped in a product without paying or asking.

- **ScheherazadeNew-Bold.ttf / -Regular.ttf** — the default. A clear modern naskh from SIL,
  designed for learners and for text with full vowel marks. Bold is used on screen so the marks
  stay visible from standing.
- **NotoNaskhArabic-Regular.ttf** — a second modern naskh, slightly narrower.
- **Amiri-Regular.ttf** — a traditional naskh, closer to a printed mushaf but finer stroked.

## About the Madinah Mushaf script

The script in the Madinah Mushaf is *KFGQPC Uthman Taha Naskh*, from the King Fahd Complex.
It is given away free for Qur'anic use, but it is not released under a licence that clearly
allows shipping it inside a commercial product. Scheherazade New Bold is the closest match
that is safe to ship. If you want the real thing, write to the King Fahd Complex for written
permission, then drop the file in here and add it to `FONTS` in `salaah/render.py`.

English uses the system font, which on Raspberry Pi OS is DejaVu Sans.

## Faces for the other scripts

- **NotoSansSC-Subset.ttf** — Simplified Chinese, for the Chinese translation.
- **NotoSansDevanagari-Subset.ttf** — Devanagari, for the Hindi translation.

Both are Noto (SIL Open Font License 1.1, see `OFL-Noto.txt`), and both are needed because
**Raspberry Pi OS ships neither script**: without them the meaning column comes out as rows of
empty boxes, and only on the device, never on a desktop that happens to have the fonts.

They are **cut down to only the characters their translation uses**, which is why they are about
140 KB each instead of the ten megabytes a whole CJK face would cost. If you change the Chinese
or Hindi wording, add characters it did not use before, and cut them again:

    python3 -m fontTools.subset /path/to/NotoSansCJK-Regular.ttc --font-number=2 \
        --text-file=chars.txt --layout-features='*' --name-IDs='*' \
        --output-file=assets/fonts/NotoSansSC-Subset.ttf

A test (`ScriptFontsTest`) checks every character of every shipping translation against the face
the app will choose for it, so a missing glyph fails the tests rather than appearing on the mat.
`Fonts.for_text` picks the face from the letters themselves, so a language added later gets the
right one without any code change — as long as its script is covered by a bundled face.
