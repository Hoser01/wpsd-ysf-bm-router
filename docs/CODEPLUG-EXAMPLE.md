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

## Two Useful Channel Styles

One-channel-per-talkgroup style:

```text
Row 535: Name DG10 LZ,       RX DG-ID 10, TX DG-ID 10, TG 3205642
Row 536: Name DG11 KCWide,   RX DG-ID 11, TX DG-ID 11, TG 313136
Row 539: Name DG22 SWMO,     RX DG-ID 22, TX DG-ID 22, TG 31291
Row 548: Name DG40 Arkansas, RX DG-ID 40, TX DG-ID 40, TG 3105
```

This keeps the radio display lined up with the DG-ID route being used.

Return-on-00 style:

```text
Row 569: Name LZ2, RX DG-ID 00, TX DG-ID 10
```

This was the working LZ test style. The radio transmits DG-ID `10` to select
the LZ route, while accepting return audio on DG-ID `00`.

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
- Radio RX DG-ID blocks return traffic. For early testing, `RX 00` is the most
  forgiving choice.
