import re
from pathlib import Path
from fontTools.ttLib import TTFont

def verify_icon_font():
    font_path = "static/vendor/fonts/material-symbols-tiny.woff2"
    font = TTFont(font_path)
    cmap = font.getBestCmap()
    glyph_to_char = {name: chr(code) for code, name in cmap.items() if 32 <= code <= 126}
    glyph_to_char['underscore'] = '_'

    gsub = font.get("GSUB")
    assert gsub and gsub.table, "GSUB missing"
    ligatures = set()
    for lookup in gsub.table.LookupList.Lookup:
        subtables = lookup.SubTable if hasattr(lookup, "SubTable") else []
        for st in subtables:
            if st.LookupType == 4:
                for first, lig_list in st.ligatures.items():
                    for lig in lig_list:
                        seq = [first] + list(lig.Component)
                        name = "".join(glyph_to_char.get(g, g) for g in seq)
                        ligatures.add(name)
            elif st.LookupType == 7:
                ext_st = st.ExtSubTable
                if ext_st.LookupType == 4:
                    for first, lig_list in ext_st.ligatures.items():
                        for lig in lig_list:
                            seq = [first] + list(lig.Component)
                            name = "".join(glyph_to_char.get(g, g) for g in seq)
                            ligatures.add(name)

    # 105 required icons
    with open("scripts/icons_subset_text.txt", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    expected_icons = lines[:-1]

    missing = [icon for icon in expected_icons if icon not in ligatures]
    assert not missing, f"Missing icons in font ligatures: {missing}"
    print(f"Font ligature verification passed: {len(expected_icons)}/105 icons present.")

def test_font_ligatures():
    verify_icon_font()

if __name__ == "__main__":
    verify_icon_font()
