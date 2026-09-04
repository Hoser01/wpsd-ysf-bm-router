# Configuration

The default configuration is TOML and is seeded in `config/ysf-bm-router.toml`.

Important sections:

- `[ysf]`: local UDP listen address, port, and reflector name.
- `[brandmeister]`: BrandMeister YSF Direct server, port, callsign, DMR ID, password, and optional DMR master settings.
- `[behavior]`: default DG-ID, default-return timer, silence period, and acknowledgment behavior.
- `[[routes]]`: DG-ID to talkgroup mappings.

## Tested BrandMeister Mode

The current tester build uses:

```toml
backend = "hybrid_dmr_return"
```

In this mode:

- YSF Direct carries outbound audio to BrandMeister.
- YSF Direct return packets are read and forwarded back to WPSD.
- The DMR master connection is kept for talkgroup context/options.
- Locally generated DMR-to-YSF return audio is not the live return path.

Recommended return behavior for the tested path:

```toml
rewrite_return_dgid = false
rewrite_return_source = false
show_dgid_callsign = false
insert_return_header = true
return_frame_interval_seconds = 0.09
return_start_delay_seconds = 0.18
```

Preserving return DG-ID and source avoids changing BrandMeister's own YSF return
frames before WPSD transmits them. Keep `show_dgid_callsign = false` for this
tester build so the VD2 source field is not decorated on return frames.

## Frequencies

`rx_frequency` and `tx_frequency` under `[brandmeister]` are used in the DMR
master registration/config packet. WPSD RF transmit and receive frequencies are
still controlled by WPSD files such as `/etc/mmdvmhost` and `/etc/ysfgateway`.

For simplex hotspot testing, all of these should agree with the radio channel:

```ini
RXFrequency=431150000
TXFrequency=431150000
```

For duplex operation, the radio must use the inverse split.

Duplicate DG-IDs are invalid. Duplicate talkgroups are allowed because the same TG may intentionally appear in more than one region or organizational group.

Configuration writes must be atomic and should preserve a backup of the previous config.

## Admin Editing

The admin UI can edit every option in `[ysf]`, `[brandmeister]`, `[behavior]`,
and `[[routes]]`. It writes the same TOML file used by the router:

```text
/opt/ysf-bm-router/config/ysf-bm-router.toml
```

Use `Apply & Restart` in the admin UI for changes that should take effect
immediately.
