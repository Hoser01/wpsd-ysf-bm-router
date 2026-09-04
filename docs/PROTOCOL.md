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

Live return-audio testing showed that raw BrandMeister YSF Direct frames can make WPSD key YSF RF while an FT5D still fails to decode audio. The DMR-master backend is therefore the preferred return-audio path. It should follow the WPSD/MMDVM bridge pattern:

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
