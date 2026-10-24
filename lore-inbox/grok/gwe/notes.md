# gwe second-read notes (Grok, session 01a14976)

Packet: issue 32 comment 6387271188. Claim 6387328704. Second-read of east game worlds batch `gwe`, limited to **MA (41), ME (12), DC (7)** in that order.

MA done; ME done; DC done.

## Scope

- Input (read-only): `research/lore-inbox/store/data/entries/gwe.jsonl` (170 entries, all `unchecked`).
- Marker file (read-only): `D:\Modding\scratch\mapmarkers\cw_markers.json` (Fallout4.esm / Commonwealth, 310 named markers).
- Output: this folder. Fold-in replaces `gwe.jsonl`, so this file holds the **whole** 170-entry batch. WV/PA/MD/OH/VA/NJ/TN/None (110 entries) are byte-for-byte the same claims with `check` still `unchecked`.
- No ids changed. No entries dropped. `label` stays `as-reported` (wiki pages, primary in-game text not opened in CK). Existing lead rulings kept.

## Second-read method

Opened fallout.wiki raw for: The_Commonwealth, Boston, Fallout_4 (Story / Pre-Production), Nuka-World_(location), Nuka-World_(add-on), Bradberton, The_Island, Far_Harbor_(add-on), Far_Harbor_(location), Capital_Wasteland. Claims match infoboxes, loading-screen quotes, Ada, Switchboard DEFCON, Nuka-World park dates, Far Harbor Bar Harbor / fog / Acadia observatory / Nucleus sub base, Capital Wasteland FO3 2277 / Rivet City carrier / Burgess GDC / cut downtown 26 to 12, Wayward patron line.

Confirmed as written: `check=checked`, `check_note=null`.
Added in-game pos from a named Commonwealth map marker: `check=corrected`, `check_note` names the marker and FormID.
Unsupported: none dropped.

## Corrected (pos added) — 19

- `GW-0009` Natick Banks FormID 0002C821 x=-86800 y=-47056
- `GW-0011` The Castle FormID 0002BCA5 x=48321.934 y=-46600.113
- `GW-0012` The Castle FormID 0002BCA5 x=48321.934 y=-46600.113
- `GW-0013` Massachusetts State House FormID 001A5B64 x=12895.229 y=-12818.047
- `GW-0014` Massachusetts State House FormID 001A5B64 x=12895.229 y=-12818.047
- `GW-0015` Old North Church FormID 0002C866 x=29036.896 y=1093.0277
- `GW-0016` Bunker Hill FormID 0002B880 x=18232.314 y=14378.211
- `GW-0017` USS Constitution FormID 00074BE0 x=27359.854 y=-3844.0212
- `GW-0019` Boston Public Library FormID 0002BB12 x=-3490.257 y=-22646.29
- `GW-0021` Boston Airport FormID 00084BEB x=48073.9 y=-3331.9624
- `GW-0022` C.I.T. Ruins FormID 0016349B x=-16793.678 y=-2777.44
- `GW-0024` Concord FormID 00082138 x=-60286.01 y=72977.79
- `GW-0025` Lexington FormID 00024F9C x=-33029.695 y=41006.22
- `GW-0026` Malden Center FormID 0002C561 x=14824.555 y=58814.344
- `GW-0027` Quincy Ruins FormID 0002C611 x=27461.742 y=-85579.984
- `GW-0028` Salem FormID 000BEB22 x=93443.66 y=80551.92
- `GW-0030` Revere Beach Station FormID 0002BA87 x=57612.566 y=29377.758
- `GW-0031` Lexington FormID 00024F9C x=-33029.695 y=41006.22
- `GW-0032` Malden Center FormID 0002C561 x=14824.555 y=58814.344

## Checked (confirmed, no pos) — 41

`GW-0001`, `GW-0002`, `GW-0003`, `GW-0004`, `GW-0005`, `GW-0006`, `GW-0007`, `GW-0008`, `GW-0010`, `GW-0018`, `GW-0020`, `GW-0023`, `GW-0029`, `GW-0033`, `GW-0034`, `GW-0035`, `GW-0036`, `GW-0037`, `GW-0038`, `GW-0039`, `GW-0040`, `GW-0041`, `GW-0042`, `GW-0043`, `GW-0044`, `GW-0045`, `GW-0046`, `GW-0047`, `GW-0048`, `GW-0049`, `GW-0050`, `GW-0051`, `GW-0052`, `GW-0053`, `GW-0054`, `GW-0055`, `GW-0056`, `GW-0057`, `GW-0058`, `GW-0063`, `GW-0170`

## Why those have no pos

- Regions / whole-map: GW-0001 Commonwealth, GW-0004 Boston, GW-0007 Glowing Sea (Edge of the Glowing Sea 0015E9A7 and Crater of Atom 000ADD89 exist; the claims are the region, not one pin).
- No named Commonwealth marker: GW-0010 Diamond City / Fenway Park (310 named markers, none named Diamond City or Fenway), GW-0018 Paul Revere Monument (Paul Revere House 001A5B68 is a different place), GW-0020 Freedom Trail, GW-0029 Nahant town (Nahant Oceanological Society / Chapel / Wharf / Sheriff only), GW-0023 Lake Quannapowitt (terminal at Nahant Oceanological Society; the claim is the lake).
- Other worldspaces: GW-0036..0040 Nuka-World / Bradberton; GW-0041..0052 The Island / Far Harbor / Acadia / Nucleus (Far Harbor worldspace). Nakano Residence is off the Commonwealth map edge and is not in cw_markers.json.
- DC / FO3: GW-0053..0058, GW-0063 Capital Wasteland (no FO4 Commonwealth pos).
- Zone write-ups without a single town pin: GW-0008 Glowing Sea guide, GW-0033 Western Commonwealth, GW-0034 Coastal Commonwealth, GW-0035 Southern Commonwealth.
- Design / quote entries with no one map pin: GW-0002 Emil 2009, GW-0003 FO4 dates, GW-0005 Ada Boston hit, GW-0006 Switchboard DEFCON, GW-0170 Making of Fallout 4 Boston photos.

## Rulings left as written

- GW-0002 Emil 2009 (tier 2 adopt): FO4 later set the Commonwealth in Massachusetts.
- GW-0008 / GW-0031..0035 guide zones (tier 2 adopt): map layout matches.
- GW-0014 State House 1969 Thirteen Commonwealths (tier 2 hold): year still only in the guide; US batch owns that check.
- GW-0057 Burgess GDC 2011 (tier 2 adopt): design statement; released map matches.
- GW-0058 cut downtown 26 to 12 (tier 3 hold): inspiration only, not adopted as fact.
- GW-0170 Making of Fallout 4 (tier 2 adopt): design statement.

## Dropped ids

None.

## Validate

From `research/lore-inbox/store`: `python tools/lore.py validate <this-folder>/verified-1.jsonl`.

Did not touch `queue-todo.tsv` (599 pages). Did not write `store/data/`. Did not run plan.ps1. Did not write game Data.
