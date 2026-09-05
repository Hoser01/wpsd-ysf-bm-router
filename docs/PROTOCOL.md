# Protocol Notes

The router must read DG-ID directly from YSF/FICH data. It must not scrape WPSD logs to infer DG-ID.

Live WPSD capture on `10.10.10.66` showed:

- `YSFP` poll packets are 14 bytes.
- `YSFD` RF frames are 155 bytes.
- `YSFD` callsign/header fields occupy the first 35 bytes.
- Encoded FICH decoding begins at byte offset `40`.
- The decoded FICH `SQ` field is the DG-ID.

Captured fixtures currently confirm:

- DG-ID `10`
- DG-ID `22`
- DG-ID `40`

An unmapped DG-ID still needs a separate capture fixture.

BrandMeister transport note: WPSD `ysf2dmr` uses the DMR/Homebrew master port, commonly `62031`. The YSF Direct login flow uses `YSFL` / `YSFACK` / `YSFK` messages and upstream YSF Direct examples use port `42001`.

Live return-audio testing showed that BrandMeister YSF Direct can carry usable
audio both directions when the WPSD RF configuration and Yaesu channel
frequencies match. The current tested backend is:

```toml
backend = "hybrid_dmr_return"
```

In this mode, outbound and return audio use BrandMeister YSF Direct. The DMR
master connection remains available for talkgroup context/options.

The local DMR-to-YSF conversion path remains experimental/reference work. If it
is revisited, it should follow the WPSD/MMDVM bridge pattern:

- parse 55-byte `DMRD` Homebrew packets
- use the DMR voice payload at bytes `20..52`
- feed voice header/data/terminator events into a converter
- emit fresh YSF frames at about 90 ms cadence
- keep DG-ID routing in this service rather than enabling a second WPSD bridge process

YSFBMDirect's public README describes the user-facing behavior we are matching:

- Add the service as a YSF reflector.
- Connect from the Yaesu radio using WIRES-X.
- Exit WIRES-X mode.
- Change the radio TX DG-ID to select the BrandMeister talkgroup.
- Suppress the short selector transmission.
- Acknowledge the route change back to the radio.
