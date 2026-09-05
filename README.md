# Fusion Hotspot Users - Channelize DMR Talkgroups!

`ysf-bm-router` is a companion service for [WPSD](https://wpsd.radio/) that lets
Yaesu System Fusion radios use DG-IDs as BrandMeister talkgroup selectors.

You can add a bank of hotspot channels to your Yaesu radio and make each channel
select a different BrandMeister talkgroup. For example, one channel can transmit
DG-ID `10` for LZ, another can transmit DG-ID `22` for SWMO, and another can
transmit DG-ID `40` for Arkansas. The router handles the BrandMeister talkgroup
selection behind the scenes.

The service installs outside WPSD-managed paths:

```text
/opt/ysf-bm-router
```

## Quick Install

SSH into the WPSD hotspot and install from GitHub:

```bash
ssh pi-star@wpsd.local

cd /home/pi-star
git clone https://github.com/Hoser01/wpsd-ysf-bm-router.git
cd wpsd-ysf-bm-router
sudo bash scripts/install.sh
```

If you already have SSH keys configured on the hotspot, this clone URL also
works:

```bash
git clone git@github.com:Hoser01/wpsd-ysf-bm-router.git
```

See [INSTALL-WPSD.md](INSTALL-WPSD.md) for the full WPSD setup order, including
required WPSD settings, the YSF host entry, backup options, and service startup.

## Required WPSD Setup

Before starting the router, WPSD should be configured like this:

- Enable System Fusion / YSF.
- Add the local YSF host entry for `YSF-BM-TEST`.
- Link YSF to `YSF-BM-TEST`.
- Keep WPSD's stock YSF2DMR service stopped/disabled for this path.
- Keep YSF X-Mode off unless you are intentionally testing WPSD's own cross-mode
  flow instead of this router.
- Confirm the radio channel frequencies match the hotspot RF setup.

The YSF host entry is:

```text
01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;
```

Add it through WPSD's persistent YSF Hosts File Editor. Do not edit generated
host files directly.

## Admin UI

After install, open:

```text
http://wpsd.local:8092/
```

Use the admin UI to verify BrandMeister credentials, backend settings, behavior
flags, and DG-ID-to-talkgroup routes. Then click `Apply & Restart`.

Detailed admin instructions are in [docs/ADMIN-UI.md](docs/ADMIN-UI.md).

## Yaesu Channels

For each BrandMeister talkgroup channel on the radio:

```text
Mode: DN
RX DG-ID: 00
TX DG-ID: the router route number
Decode/SQL: OFF
Frequency: match the hotspot RF setup
```

Example:

```text
Name: DG10 LZ
RX DG-ID: 00
TX DG-ID: 10
Router route: DG-ID 10 -> BrandMeister TG 3205642
```

See [docs/CODEPLUG-EXAMPLE.md](docs/CODEPLUG-EXAMPLE.md) for a complete generic
codeplug pattern.

## More Docs

- [docs/CURRENT-TESTED-STATE.md](docs/CURRENT-TESTED-STATE.md)
- [docs/ADMIN-UI.md](docs/ADMIN-UI.md)
- [docs/CODEPLUG-EXAMPLE.md](docs/CODEPLUG-EXAMPLE.md)
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m pytest
```

## Acknowledgments

Thanks to Chip Cuccio, `W0CHP`, for WPSD and the hotspot platform this project
is designed to complement:

https://wpsd.radio/

This project was inspired by YSFBMDirect by Stefano IS0EIR:

https://github.com/stefanolande/YSFBMDirect

Selected YSF decoder pieces are vendored with attribution. See
[THIRD_PARTY.md](THIRD_PARTY.md).
