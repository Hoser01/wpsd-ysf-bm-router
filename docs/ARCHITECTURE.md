# Architecture

`ysf-bm-router` runs beside WPSD as an independent service. WPSD should see it as a local YSF reflector, not as a patch to WPSD internals.

```text
Yaesu FT5D
  -> MMDVMHost / WPSD
  -> YSFGateway
  -> ysf-bm-router
  -> BrandMeister YSF Direct
```

## Boundaries

The application owns `/opt/ysf-bm-router` and, optionally, a small WPSD dashboard symlink such as `/var/www/dashboard/admin/ysfbm`.

It must not overwrite:

- `/etc/ysf2dmr`
- `/etc/dgidgateway`
- `/usr/local/bin/YSF2DMR`
- `/usr/local/bin/YSFGateway`
- `/usr/local/bin/DMRGateway`
- WPSD dashboard source files, except for a safe link or similar integration point

## Modules

- `ysf`: YSF packet parsing, FICH handling, and future YSF frame generation.
- `router`: DG-ID lookup, active route state, selector suppression, silence protection, and default route return.
- `brandmeister`: transport boundary for BrandMeister YSF Direct login, keepalive, talkgroup selection, and return packets.
- `dmr`: Homebrew DMR packet parsing for the DMR-master backend.
- `bridge`: AMBE/voice frame repacking helpers used by the experimental DMR-to-YSF return path.
- `web`: future localhost control API and WPSD-integrated UI.
- `scripts`: install, uninstall, and WPSD integration repair scripts.

## Licensing

YSFBMDirect by Stefano IS0EIR is licensed under GNU GPL version 3. The upstream repository inspected for this project is:

https://github.com/stefanolande/YSFBMDirect

Observed upstream commit: `76f834b400af8b292e9b980742f81e4f4e738470`.

Because YSFBMDirect is GPLv3, copied or adapted implementation code requires GPL-compatible distribution terms and preservation of notices. This project is therefore initialized as `GPL-3.0-or-later`.

Selected YSF FICH decoder components are vendored under `src/ysf_bm_router/vendor/pysfreflector` with original headers preserved. See `THIRD_PARTY.md`.

The DMR-to-YSF backend is based on WPSD/MMDVM-family source behavior. The relevant reference code builds fresh YSF header/data/terminator frames from DMR voice frames using `ModeConv`, with 55 ms DMR frame cadence and 90 ms YSF frame cadence. That source is GPL-2.0-or-later and credits Jonathan Naylor G4KLX, Mathias Weyland HB9FRV, Andy Uribe CA6JAU, Manuel Sanchez EA7EE, AD8DP, and others. Code ported from that path must preserve GPL-compatible licensing and attribution.

The current tested live path does not rely on locally generated DMR-to-YSF return audio. It uses BrandMeister YSF Direct packets for outbound and inbound audio, while the DMR master connection is retained for talkgroup context/options in `hybrid_dmr_return` mode.

## First Milestone

The first functional milestone is:

1. Accept traffic from YSFGateway on `127.0.0.1:42002`.
2. Decode DG-ID `10`.
3. Select BrandMeister TG `3205642`.
4. Decode DG-ID `22`.
5. Select BrandMeister TG `31291`.
6. Suppress the selector transmission.
7. Send an acknowledgment frame back to the Yaesu radio.

The current code implements the route/config model, switching decision state, raw `YSFD` frame parsing for captured WPSD frames where the encoded FICH begins at byte `40`, BrandMeister YSF Direct transport, Homebrew `DMRD` frame parsing, and experimental DMR-to-YSF AMBE repacking helpers.
