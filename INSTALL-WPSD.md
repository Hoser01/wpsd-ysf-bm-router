# Install On WPSD Over SSH

These instructions assume you are SSH'ing into a WPSD hotspot and installing the
router directly on that hotspot.

The router installs to:

```text
/opt/ysf-bm-router
```

That path is intentionally outside WPSD-managed dashboard and binary paths, so
normal WPSD updates should not overwrite the router files.

## 1. Required WPSD Settings

Before starting the router, verify WPSD is set up for the router path:

```text
System Fusion / YSF: enabled
YSF linked host: YSF-BM-TEST
Stock WPSD YSF2DMR: stopped/disabled for this path
YSF X-Mode: off
Radio mode: simplex or duplex to match your hotspot hardware
```

The router handles the BrandMeister talkgroup selection. WPSD should not also
run its own YSF2DMR bridge against the same traffic path.

Frequency details are covered in [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## 2. Add The WPSD YSF Host Entry

In the WPSD dashboard, open the persistent YSF Hosts File Editor and add:

```text
01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;
```

Then link YSF to `YSF-BM-TEST`.

Do not edit WPSD-generated host files directly.

## 3. Backup First

Before installing experimental hotspot software, consider imaging your existing
WPSD microSD card so you can return the hotspot to its current state.

See [docs/BACKUP-WPSD.md](docs/BACKUP-WPSD.md) for the full backup checklist.

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

## 4. Install From GitHub

SSH into the hotspot. Replace `wpsd.local` with the hotspot IP address if mDNS
does not resolve.

```bash
ssh pi-star@wpsd.local
```

Default WPSD SSH credentials are commonly:

```text
username: pi-star
password: raspberry
```

Use your own hostname, username, or password if the hotspot has been changed.

On the hotspot:

```bash
cd /home/pi-star
git clone https://github.com/Hoser01/wpsd-ysf-bm-router.git
cd wpsd-ysf-bm-router
sudo bash scripts/install.sh
```

If SSH keys are configured on the hotspot, you can clone with SSH instead:

```bash
git clone git@github.com:Hoser01/wpsd-ysf-bm-router.git
```

## 5. Installer Behavior

The installer will:

1. Install application files under `/opt/ysf-bm-router`.
2. Preserve an existing `/opt/ysf-bm-router/config/ysf-bm-router.toml`.
3. Install `ysf-bm-router.service`.
4. Install `ysf-bm-router-admin.service`.
5. Reload systemd.
6. Enable and restart the admin UI.
7. Print the YSF Hosts File Editor entry.
8. Print the admin UI URL.

The installer does not start the main router service automatically, because
BrandMeister credentials and routes should be reviewed first.

## 6. Verify Settings In The Admin UI

Open the admin interface from a browser on the same network:

```text
http://wpsd.local:8092/
```

If `wpsd.local` does not resolve, use the hotspot IP address:

```text
http://HOTSPOT_IP_ADDRESS:8092/
```

In the admin UI, verify:

- BrandMeister server and YSF Direct port.
- Callsign.
- DMR ID, including hotspot suffix if you use one.
- Hotspot security password.
- Backend is `hybrid_dmr_return`.
- DMR master server, port, password, and options.
- Behavior flags match the tested defaults.
- Every radio TX DG-ID has a matching enabled route.
- Each route points to the intended BrandMeister talkgroup.

Then click `Apply & Restart`. The admin UI writes the config, validates it,
keeps a `.bak` backup, restarts the router service, and shows onscreen status.

See [docs/ADMIN-UI.md](docs/ADMIN-UI.md) for the complete admin checklist and
talkgroup route instructions.

## 7. Manual Config Option

If you prefer to edit the TOML directly:

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
ysf-bm-router --config /opt/ysf-bm-router/config/ysf-bm-router.toml --check-config
sudo systemctl restart ysf-bm-router.service
journalctl -u ysf-bm-router -n 50 --no-pager
```

## 8. Start Or Restart The Router

After admin verification:

```bash
sudo systemctl stop ysf2dmr.service ysf2dmr.timer
sudo systemctl enable --now ysf-bm-router.service
```

For later restarts:

```bash
sudo systemctl restart ysf-bm-router.service
```
