# Current Tested State

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
- Return traffic works with Yaesu channel `RX DG-ID 00`.
- The app runs from `/opt/ysf-bm-router` so WPSD updates should not overwrite it.

The DMR/Homebrew conversion code remains in the tree as experimental/reference
work. The current tester build uses BrandMeister YSF Direct for live audio both
ways with:

```toml
backend = "hybrid_dmr_return"
```

The no-audio return issue seen during testing was caused by an RF frequency
mismatch on the hotspot. The radio was receiving on one frequency while the
hotspot was transmitting on another, so the FT5D lit green/flickered but did not
decode valid C4FM audio. See [CONFIGURATION.md](CONFIGURATION.md) and
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) for frequency checks.
