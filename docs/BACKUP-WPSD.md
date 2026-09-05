# Back Up WPSD Before Testing

`ysf-bm-router` is alpha software. Before installing it on a working hotspot,
make a backup you can restore from.

## Option 1: Full microSD Image

A full microSD image is the safest rollback path because it captures WPSD, the
operating system, service state, and local configuration.

On Windows, one common tool is:

```text
Win32 Disk Imager
https://sourceforge.net/projects/win32diskimager/
```

Basic process:

1. Shut down the hotspot cleanly.
2. Remove the microSD card.
3. Insert the microSD card into your computer.
4. Open Win32 Disk Imager.
5. Select the correct drive letter for the microSD card.
6. Choose a destination `.img` filename.
7. Use the read/backup option to save the card image.

Double-check the selected drive letter before reading or writing any SD card
image.

To restore, write the saved `.img` back to the same card or to a replacement
card.

## Option 2: WPSD Backup/Restore

Use WPSD's dashboard Backup/Restore feature before changing hotspot settings.
This is faster than a full image and is useful for normal WPSD configuration,
but it is not the same as a complete microSD image.

Recommended approach:

1. Make a WPSD Backup/Restore export.
2. Save the exported backup somewhere off the hotspot.
3. Still consider a full microSD image before broad testing.

## Router Config Backup

The installer preserves an existing router config at:

```text
/opt/ysf-bm-router/config/ysf-bm-router.toml
```

The admin UI also creates:

```text
/opt/ysf-bm-router/config/ysf-bm-router.toml.bak
```

For router-only rollback, copy your known-good `ysf-bm-router.toml` back into
`/opt/ysf-bm-router/config/` and restart:

```bash
sudo systemctl restart ysf-bm-router.service
```
