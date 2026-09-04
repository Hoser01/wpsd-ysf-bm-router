# Troubleshooting

## WPSD Cannot Connect To Router

- Verify `ysf-bm-router.service` is active.
- Verify the service is listening on `127.0.0.1:42002`.
- Verify the custom YSF host entry was added through WPSD's persistent Hosts File Editor.

## DG-ID Does Not Change Talkgroup

- Confirm the FT5D channel is transmitting C4FM/DN.
- Confirm TX DG-ID is set on the radio.
- Confirm the DG-ID exists and is enabled in the route table.
- Check whether the silence protection window is blocking rapid changes.

## BrandMeister Does Not Connect

- Verify callsign, DMR ID, server, port, and hotspot security password.
- Confirm the password is not exposed through logs or API responses.
- Check service logs with `journalctl -u ysf-bm-router`.

## Radio Lights Green Or Flickers But Has No Fusion Audio

This usually means the radio is seeing RF energy but not decoding valid C4FM on
the channel it is listening to.

First check the WPSD RF frequencies:

```bash
grep -n "Frequency" /etc/mmdvmhost /etc/ysfgateway
```

For simplex, the hotspot TX and RX frequencies must both match the radio:

```ini
RXFrequency=431150000
TXFrequency=431150000
```

For duplex:

- Radio TX equals hotspot RX.
- Radio RX equals hotspot TX.

This project was proven after correcting a test hotspot that was receiving on
`431.150000 MHz` but transmitting on `426.150000 MHz`.

## Return Audio Does Not Reach The Yaesu Radio

- Use `backend = "hybrid_dmr_return"` for the current tested path.
- Use `rewrite_return_source = false` so BrandMeister YSF Direct return frames are preserved.
- Use `rewrite_return_dgid = false` unless deliberately forcing return traffic to a local DG-ID.
- Use `show_dgid_callsign = false` so return-frame VD2 source fields are not decorated.
- Confirm WPSD shows the router host as linked.
- Confirm `/etc/mmdvmhost` has `[System Fusion] Enable=1`.
- Confirm stock `ysf2dmr.service` is stopped if it conflicts with this router.

## Useful Logs

```bash
journalctl -u ysf-bm-router -n 100 --no-pager
tail -100 /var/log/pi-star/MMDVM-$(date +%F).log
tail -100 /var/log/pi-star/YSFGateway-$(date +%F).log
```
