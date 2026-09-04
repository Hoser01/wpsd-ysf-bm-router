# Install On WPSD Over SSH

These instructions assume you are deploying from your computer to a WPSD
hotspot over SSH.

Target install path:

```text
/opt/ysf-bm-router
```

This path is intentionally outside WPSD-managed dashboard and binary paths.
WPSD updates should not overwrite the router files.

Initial WPSD local reflector entry:

```text
01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;
```

Add that entry through WPSD's persistent YSF Hosts File Editor. Do not edit WPSD-generated host files directly.

## 0. Backup First

Before installing experimental hotspot software, consider imaging your existing
WPSD microSD card so you can return the hotspot to its current state.

Recommended Windows imaging tool:

```text
Win32 Disk Imager
https://sourceforge.net/projects/win32diskimager/
```

Use the tool's read/backup option to save the whole microSD card to an `.img`
file. Double-check the selected drive letter before reading or writing any SD
card image.

Backup options:

- Full rollback: power down the hotspot, remove the microSD card, and make a
  full `.img` backup with Win32 Disk Imager or another raw disk imaging tool.
- Quick WPSD restore: use the WPSD dashboard backup/export option for the normal
  WPSD configuration before making changes.
- Manual router restore: the installer preserves an existing
  `/opt/ysf-bm-router/config/ysf-bm-router.toml`; keep a copy of that file if
  you already have a working router configuration.

Restore options:

- Full restore: write the saved `.img` back to the microSD card.
- WPSD config restore: use the WPSD dashboard restore/import option.
- Router-only restore: copy your saved `ysf-bm-router.toml` back to
  `/opt/ysf-bm-router/config/` and restart `ysf-bm-router.service`.

## 1. Copy The Deploy Zip To The Hotspot

From your computer, copy the deploy zip to the hotspot. Replace `wpsd.local`
with the hotspot IP address if mDNS does not resolve.

```bash
scp ysf-bm-router-0.1.0-test-20260904.zip pi-star@wpsd.local:/home/pi-star/
```

Default WPSD SSH credentials are commonly:

```text
username: pi-star
password: raspberry
```

Use your own hostname, username, or password if the hotspot has been changed.

## 2. SSH Into The Hotspot

```bash
ssh pi-star@wpsd.local
```

## 3. Unzip And Run The Installer

On the hotspot:

```bash
cd /home/pi-star
unzip -o ysf-bm-router-0.1.0-test-20260904.zip -d ysf-bm-router
cd ysf-bm-router
sudo bash scripts/install.sh
```

## Installer Behavior

The installer will:

1. Install application files under `/opt/ysf-bm-router`.
2. Preserve an existing `/opt/ysf-bm-router/config/ysf-bm-router.toml`.
3. Install `ysf-bm-router.service`.
4. Install `ysf-bm-router-admin.service`.
5. Reload systemd.
6. Print the YSF Hosts File Editor entry.
7. Print the admin UI URL.

The installer enables and starts the admin UI automatically. It does not start
the main router service automatically, because BrandMeister credentials and
routes should be reviewed first. Stop WPSD's stock YSF2DMR service before
starting this router so both programs do not try to own the BrandMeister path.

```bash
sudo systemctl stop ysf2dmr.service ysf2dmr.timer
sudo systemctl enable --now ysf-bm-router.service
```

## 4. Configure Router In The Admin UI

Open the admin interface from a browser on the same network:

```text
http://wpsd.local:8092/
```

If `wpsd.local` does not resolve, use the hotspot IP address:

```text
http://HOTSPOT_IP_ADDRESS:8092/
```

The admin interface is separate from WPSD and lives with this project under
`/opt/ysf-bm-router`. It edits `/opt/ysf-bm-router/config/ysf-bm-router.toml`,
creates a `.bak` backup when saving, validates the full config, and shows
onscreen apply/restart status.

You can configure all router sections from the admin UI:

- YSF listener settings.
- BrandMeister YSF Direct and DMR master settings.
- Behavior flags and timers.
- DG-ID route mappings.

Use `Apply & Restart` after edits so the running router picks up the new
configuration.

## 5. Configure Router Manually

Edit:

```bash
sudo nano /opt/ysf-bm-router/config/ysf-bm-router.toml
```

Required tester values:

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
```

`dmr_id` should be the extended hotspot ID when using one. For example, a
subscriber ID of `3129301` with hotspot suffix `10` becomes `312930110`.

After changes:

```bash
sudo systemctl restart ysf-bm-router.service
journalctl -u ysf-bm-router -n 50 --no-pager
```

## 6. Add The WPSD YSF Host Entry

In the WPSD dashboard, open the persistent YSF Hosts File Editor and add:

```text
01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;
```

Then link YSF to `YSF-BM-TEST`.

## 7. WPSD Frequency Check

For simplex testing, confirm MMDVMHost and YSFGateway transmit on the same
frequency the radio is listening on:

```bash
grep -n "Frequency" /etc/mmdvmhost /etc/ysfgateway
```

Example simplex result:

```ini
RXFrequency=431150000
TXFrequency=431150000
```

For duplex, the radio channel must use the opposite split:

- Radio TX equals hotspot RX.
- Radio RX equals hotspot TX.

## 8. Config Check

```bash
ysf-bm-router --config /opt/ysf-bm-router/config/ysf-bm-router.toml --check-config
```
