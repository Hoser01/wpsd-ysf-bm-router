# Tester Quickstart

This guide is for WPSD testers validating `ysf-bm-router`.

Before testing, consider imaging the existing WPSD microSD card. A full card
image is the fastest way to roll the hotspot back to its current known-good
state. On Windows, Win32 Disk Imager can read a removable SD card into a raw
`.img` file:

```text
https://sourceforge.net/projects/win32diskimager/
```

WPSD's dashboard backup/export is also useful for normal WPSD configuration,
but it is not the same as a full microSD image.

## 1. Copy The Zip To The Hotspot

From your computer:

```bash
scp ysf-bm-router-0.1.0-test-20260904.zip pi-star@wpsd.local:/home/pi-star/
```

If `wpsd.local` does not resolve, use the hotspot IP address.

## 2. SSH Into The Hotspot

```bash
ssh pi-star@wpsd.local
```

Use the hotspot's current SSH username and password.

## 3. Unzip And Install

On the hotspot:

```bash
cd /home/pi-star
unzip -o ysf-bm-router-0.1.0-test-20260904.zip -d ysf-bm-router
cd ysf-bm-router
sudo bash scripts/install.sh
```

The installer copies files to:

```text
/opt/ysf-bm-router
```

## 4. Configure

The installer starts the admin UI automatically.

Open:

```text
http://wpsd.local:8092/
```

Use the hotspot IP address if `wpsd.local` does not resolve. The admin page can
edit every router config option and shows save/restart status onscreen.

Minimum required values are:

```toml
[brandmeister]
server = "3102.repeater.net"
port = 42001
callsign = "YOURCALL"
dmr_id = "YOURDMRIDSS"
password = "YOUR_HOTSPOT_SECURITY_PASSWORD"
backend = "hybrid_dmr_return"
master_server = "3103.master.brandmeister.network"
master_port = 62031
master_password = "YOUR_HOTSPOT_SECURITY_PASSWORD"
master_options = "TS2_1=3205642;"

[behavior]
rewrite_return_dgid = false
rewrite_return_source = false
show_dgid_callsign = false
insert_return_header = true
```

Set `master_options` to the default/startup talkgroup for the test. The supplied
route table maps DG-ID `10` to TG `3205642`.

Manual fallback:

```bash
sudo nano /opt/ysf-bm-router/config/ysf-bm-router.toml
```

## 5. Add WPSD YSF Host

In WPSD, use the persistent YSF Hosts File Editor and add:

```text
01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;
```

Then link YSF to `YSF-BM-TEST`.

## 6. Stop Conflicting Service

```bash
sudo systemctl stop ysf2dmr.service ysf2dmr.timer 2>/dev/null || true
```

## 7. Start Router

```bash
sudo systemctl enable --now ysf-bm-router.service
journalctl -u ysf-bm-router -n 50 --no-pager
```

## 8. Verify Hotspot Frequencies

For simplex, the hotspot TX/RX and radio frequency must match:

```bash
grep -n "Frequency" /etc/mmdvmhost /etc/ysfgateway
```

Example:

```ini
RXFrequency=431150000
TXFrequency=431150000
```

For duplex, program the radio with the inverse split:

- Radio TX equals hotspot RX.
- Radio RX equals hotspot TX.

## 9. Radio Setup

Use DN mode. For the current LZ test, the FT5D CSV example at row `569` uses:

- RX DG-ID: `00`
- TX DG-ID: `10`

Key once on DG-ID `10` to select the LZ route. Return traffic should come back
on DG-ID `00`.

Rows `535` and later in the example FT5D CSV also show one-channel-per-DG-ID
entries, where each channel uses matching RX/TX DG-IDs for the mapped route.
See [CODEPLUG-EXAMPLE.md](CODEPLUG-EXAMPLE.md).

## 10. Report Back

Please report:

- WPSD version and modem type.
- Hotspot simplex or duplex.
- Radio model.
- Whether outbound YSF to BrandMeister worked.
- Whether inbound audio returned to the Yaesu radio.
- Any dashboard target/callsign oddities.
- The last 100 router log lines if it failed:

```bash
journalctl -u ysf-bm-router -n 100 --no-pager
```
