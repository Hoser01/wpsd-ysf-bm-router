# Admin UI

`ysf-bm-router` includes a separate admin interface for editing router settings
without modifying WPSD dashboard files.

Default URL:

```text
http://wpsd.local:8092/
```

Use the hotspot IP address if `wpsd.local` does not resolve.

## WPSD Theme Matching

The admin UI reads WPSD's selected dashboard color config from:

```text
/etc/wpsd-css.ini
```

Those colors are mapped into the admin page as CSS variables, so the router UI
tracks the currently selected WPSD dashboard appearance without installing files
inside WPSD's dashboard source tree.

If `/etc/wpsd-css.ini` is missing or unreadable, the admin UI falls back to its
built-in dark LZ-style palette.

The installer enables and restarts the admin service automatically. It runs
separately from the router service:

```bash
sudo systemctl enable --now ysf-bm-router-admin.service
sudo systemctl status ysf-bm-router-admin.service
```

The interface can edit every option in:

- `[ysf]`
- `[brandmeister]`
- `[behavior]`
- `[[routes]]`

## Settings To Verify

Before clicking `Apply & Restart`, verify these fields.

YSF listener:

- Listen host is `127.0.0.1`.
- Listen port is `42002`.
- Reflector name matches the WPSD host entry, usually `YSF-BM-TEST`.

BrandMeister:

- YSF Direct server is correct for your region.
- YSF Direct port is `42001`.
- Callsign is your hotspot callsign.
- DMR ID includes the hotspot suffix if you use one.
- Password is your BrandMeister hotspot security password.
- Backend is `hybrid_dmr_return`.
- DMR master server and port are correct.
- DMR master password matches the hotspot security password.
- Master options contain the startup talkgroup you want, such as
  `TS2_1=3205642;`.

Behavior:

- `rewrite_return_dgid` is off for the tested generic Yaesu setup.
- `rewrite_return_source` is off for the tested generic Yaesu setup.
- `show_dgid_callsign` is off for the tested generic Yaesu setup.
- `insert_return_header` is on.
- Return frame interval and start delay are left at the tested defaults unless
  you are intentionally experimenting.

Routes:

- Every Yaesu channel TX DG-ID has one matching enabled route.
- Each route points to the intended BrandMeister talkgroup.
- DG-ID values are unique.
- Route names are short enough to scan quickly in the admin UI.

WPSD:

- System Fusion / YSF is enabled.
- The `YSF-BM-TEST` host entry exists in WPSD.
- WPSD is linked to `YSF-BM-TEST`.
- WPSD's stock YSF2DMR service is stopped/disabled for this path.
- YSF X-Mode is off unless you are intentionally testing WPSD's own cross-mode
  flow instead of this router.

Yaesu radio:

- Each channel is in DN mode.
- Each channel uses `RX DG-ID 00`.
- Each channel uses `TX DG-ID` equal to the desired router route.

See [CODEPLUG-EXAMPLE.md](CODEPLUG-EXAMPLE.md) for exact channel examples.

When you click `Apply & Restart`, the admin service:

1. Builds a complete router config from the form.
2. Validates it with the same model used by the router.
3. Writes `/opt/ysf-bm-router/config/ysf-bm-router.toml` atomically.
4. Preserves the previous file as `ysf-bm-router.toml.bak`.
5. Restarts `ysf-bm-router.service`.
6. Shows the save and restart status onscreen.

Use `Save Only` when preparing changes that should not take effect until a
later manual restart.

Security note: the admin UI is intended for trusted hotspot LAN access. Do not
forward port `8092` to the internet.
