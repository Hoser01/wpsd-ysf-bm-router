# Yaesu Codeplug Example

The router lets a Yaesu Fusion radio use DG-IDs like channel selectors for
BrandMeister talkgroups. Program one Yaesu memory channel per BrandMeister
talkgroup you want quick access to.

## Channel Pattern

Use this pattern for each router channel:

```text
Channel name: short talkgroup label
Receive frequency: hotspot transmit frequency
Transmit frequency: hotspot receive frequency
Mode: DN
AMS/Mode behavior: fixed DN is recommended
Repeater shift: OFF for simplex, correct split for duplex
Decode/SQL type: OFF
DG-ID SQL: 023
RX DG-ID: 00
TX DG-ID: mapped router DG-ID
RX/TX mode: RX Normal TX Normal
TX power: low or reduced power appropriate for your hotspot
Step: 25.0 kHz
```

For a simplex hotspot, the channel RX and TX frequencies are usually the same:

```text
Radio RX Frequency = hotspot TX frequency
Radio TX Frequency = hotspot RX frequency
```

For a duplex hotspot, program the radio with the inverse split:

```text
Radio TX Frequency = hotspot RX frequency
Radio RX Frequency = hotspot TX frequency
```

Frequency details and WPSD checks are in
[CONFIGURATION.md](CONFIGURATION.md#frequencies).

## DG-ID Pattern

For normal use:

```text
RX DG-ID = 00
TX DG-ID = route DG-ID
```

The radio transmits the route DG-ID to select the BrandMeister talkgroup. Return
traffic is most compatible when the Yaesu channel receives DG-ID `00`.

## Example Channels

These are example channel values using a simplex hotspot on `431.150000 MHz`.
Use your own hotspot frequency and route list.

```text
Name: DG10 LZ
RX Frequency: 431.150000
TX Frequency: 431.150000
Mode: DN
RX DG-ID: 00
TX DG-ID: 10
Router route: DG-ID 10 -> BrandMeister TG 3205642
```

```text
Name: DG22 SWMO
RX Frequency: 431.150000
TX Frequency: 431.150000
Mode: DN
RX DG-ID: 00
TX DG-ID: 22
Router route: DG-ID 22 -> BrandMeister TG 31291
```

```text
Name: DG40 AR
RX Frequency: 431.150000
TX Frequency: 431.150000
Mode: DN
RX DG-ID: 00
TX DG-ID: 40
Router route: DG-ID 40 -> BrandMeister TG 3105
```

## Matching Router Routes

Every radio TX DG-ID must exist in the router route table. You can add and edit
routes in the admin UI or directly in `ysf-bm-router.toml`.

Example route:

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

## Common Mistakes

- Radio channel is in FM instead of DN.
- Radio channel frequency does not match the hotspot RF setup.
- Simplex hotspot has different WPSD TX/RX frequencies.
- Duplex hotspot channel does not use the inverse split.
- Radio TX DG-ID is not mapped in the router route table.
- Radio RX DG-ID blocks return traffic. Use `RX DG-ID 00` for the generic setup.
