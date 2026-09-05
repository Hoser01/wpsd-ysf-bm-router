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
