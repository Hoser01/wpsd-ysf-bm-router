# ysf-bm-router

`ysf-bm-router` is a WPSD companion service that presents itself as a local YSF reflector and maps Yaesu System Fusion DG-ID values to BrandMeister talkgroups.

The service is designed to live outside WPSD-managed files under:

```text
/opt/ysf-bm-router
```

## Current Tested State

The current working path is:

```text
Yaesu radio
  -> MMDVMHost / WPSD
  -> YSFGateway
  -> ysf-bm-router on 127.0.0.1:42002
  -> BrandMeister YSF Direct
  -> BrandMeister return audio
  -> ysf-bm-router
  -> YSFGateway / MMDVMHost
  -> Yaesu radio
```

Confirmed on WPSD with an FT5D:

- YSF/DN outbound from the radio reaches BrandMeister.
- BrandMeister return audio reaches the FT5D.
- DG-ID values select configured BrandMeister talkgroups.
- The app runs from `/opt/ysf-bm-router` so WPSD updates should not overwrite it.

The DMR/Homebrew conversion code remains in the tree as experimental/reference work. The current tester build uses BrandMeister YSF Direct for live audio both ways.

## WPSD Host Entry

Add this through WPSD's persistent YSF Hosts File Editor:

```text
01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;
```

Do not edit generated host files directly.

## Install

For tester deployment, SSH into the WPSD hotspot, unzip the deploy package on
the hotspot, then run `sudo bash scripts/install.sh`. See
[INSTALL-WPSD.md](INSTALL-WPSD.md) for the full SSH deployment flow, including
microSD backup and restore options.

## Admin UI

The package includes a separate dark admin interface at:

```text
http://wpsd.local:8092/
```

It runs as `ysf-bm-router-admin.service`, edits this project's TOML config under
`/opt/ysf-bm-router`, validates changes before writing, creates a `.bak` backup,
and shows save/restart status onscreen. See [docs/ADMIN-UI.md](docs/ADMIN-UI.md).

## Frequency Requirement

For simplex hotspot operation, WPSD/MMDVMHost TX and RX must both match the radio channel:

```ini
RXFrequency=431150000
TXFrequency=431150000
```

For duplex hotspot operation:

- Radio TX must equal hotspot RX.
- Radio RX must equal hotspot TX.

If the hotspot transmits on a different frequency than the radio is listening to, the radio may light green or flicker but will not decode valid C4FM audio.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m pytest
```

## Acknowledgments

This project was inspired by YSFBMDirect by Stefano IS0EIR:

https://github.com/stefanolande/YSFBMDirect

Selected YSF decoder pieces are vendored with attribution. See [THIRD_PARTY.md](THIRD_PARTY.md).
