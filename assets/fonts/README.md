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

- **NotoSansSC-Subset.ttf** — Simplified Chinese.
- **NotoSansDevanagari-Subset.ttf** — Devanagari, for Hindi.
- **NotoSansBengali-Subset.ttf** — Bengali, added in 1.84.

All three are Noto (SIL Open Font License 1.1, see `OFL-Noto.txt`), and all three are needed
because **Raspberry Pi OS ships none of those scripts**: without them the words come out as rows
of empty boxes, and only on the device, never on a desktop that happens to have the fonts.

### Cut them again whenever the wording changes

This is the instruction that was already here and was not followed, so it is worth saying what
it cost. The Chinese face was cut from the **translation** text and never recut as the interface
grew. By 1.84 the Chinese pack had gained the Wi-Fi, Bluetooth, radio and wu'du screens, and
**96 of the Han characters it used were not in the font** — 88 of its 287 strings would have
shown at least one empty box on a Pi, including 搜索 (search), 毯 (mat) and 备 (device). The
translation was still perfect, which is why nothing looked wrong.

So: the set to cut to is **the interface pack AND the translation**, not either one alone.

    python3 -m fontTools.subset <source font> --text-file=chars.txt \
        --layout-features='*' --name-IDs='*' --notdef-outline \
        --output-file=assets/fonts/NotoSansSC-Subset.ttf

Sources, all reachable from GitHub: `notofonts/noto-cjk` for
`Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf`, and `notofonts/notofonts.github.io` for
`fonts/NotoSansDevanagari/...` and `fonts/NotoSansBengali/...`.

### Han by character, Indic by whole block

Chinese is cut to the characters in use: Han has no decomposition, there is nothing to build a
character out of, and the whole face is ten megabytes.

Devanagari and Bengali are cut to **the whole of their Unicode block**. They are Indic scripts:
conjuncts are assembled by the font's own substitution rules out of letters that may never
appear on screen themselves, so "the characters the words use" is the wrong set to cut to. The
block entire costs about 50 KB more than the characters in use, which is cheaper than finding
out on the device which conjunct is missing. `--layout-features='*'` keeps GSUB, GPOS and GDEF,
without which the letters arrive but do not join up.

Devanagari showed the smaller version of the same fault: ज़ (U+095B) was not in the font and only
rendered because Qt decomposed it into ज plus a nukta, both of which were. Correct on screen,
and resting on something no test had checked.

### What the tests check

`ScriptFontsTest` checks every character of every shipping translation AND of every interface
pack against the face the app chooses for it — reading the glyph table out of the font file
rather than asking Qt, because `QFontMetrics.inFont` answers from whatever face Qt would
substitute and so says yes to characters the chosen file has never heard of. That is exactly how
both faults above went unnoticed. It also checks that a shared Indic full stop cannot decide
which face a language gets; see `Fonts.for_text`.
`Fonts.for_text` picks the face from the letters themselves, so a language added later gets the
right one without any code change — as long as its script is covered by a bundled face.
