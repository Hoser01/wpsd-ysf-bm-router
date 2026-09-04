# Yaesu Codeplug Example

The router lets a Yaesu Fusion radio use DG-IDs like channel selectors for
BrandMeister talkgroups. The supplied test config maps DG-ID `10` to TG
`3205642`, DG-ID `22` to TG `31291`, and so on.

## FT5D / ADMS Pattern

Rows `535` and later in the test FT5D CSV show the intended pattern:

```text
Frequency: 431.150000 MHz
Mode: DN
Repeater shift: OFF for simplex hotspot testing
SQL/Decode type: OFF
DG-ID SQL: 023
RX/TX mode: RX Normal TX Normal
TX power: as appropriate for your hotspot, usually Low or reduced power
```

For a simplex hotspot, the channel RX and TX frequencies should both match the
hotspot frequency. In the working test, that was:

```text
RX Frequency: 431.150000
TX Frequency: 431.150000
```

For a duplex hotspot, program the radio with the inverse split:

```text
Radio TX = hotspot RX
Radio RX = hotspot TX
```

## Recommended DG-ID Pattern

For normal use, set the channel's TX DG-ID to the route you want to select and
set RX DG-ID to `00`.

```text
RX DG-ID = 00
TX DG-ID = mapped router DG-ID
```

Examples:

```text
Name DG10 LZ:       RX DG-ID 00, TX DG-ID 10, TG 3205642
Name DG11 KCWide:   RX DG-ID 00, TX DG-ID 11, TG 313136
Name DG22 SWMO:     RX DG-ID 00, TX DG-ID 22, TG 31291
Name DG40 Arkansas: RX DG-ID 00, TX DG-ID 40, TG 3105
```

The radio transmits the mapped DG-ID to select the BrandMeister talkgroup. Return
traffic normally comes back on DG-ID `00`, so `RX 00` is the most forgiving
receive setting across radios and hotspots.

## FT5D CSV Rows

Rows `535` and later in the development FT5D CSV were used while testing this
pattern. Row `569` is the clean example for the current recommendation:

```text
Row 569: Name LZ2, RX DG-ID 00, TX DG-ID 10
```

Earlier rows used matching RX/TX DG-IDs while we were testing route selection.
Those can still work in some setups, but `RX 00` with a mapped TX DG-ID is the
recommended generic codeplug pattern.

## Matching Router Routes

The radio TX DG-ID must exist in `ysf-bm-router.toml`:

```toml
[[routes]]
dgid = 10
talkgroup = 3205642
short_name = "LZ"
long_name = "N0NMS / LZ"
region = "LZ"
sort_order = 10
enabled = true
```

If you create additional radio channels, add matching `[[routes]]` entries in
the router config or through the admin UI.

## Common Mistakes

- Radio is in FM instead of DN.
- Radio channel frequency does not match the hotspot transmit frequency.
- Simplex hotspot has different WPSD TX/RX frequencies.
- Radio TX DG-ID is not mapped in the router route table.
- Radio RX DG-ID blocks return traffic. Use `RX 00` for the generic setup.
