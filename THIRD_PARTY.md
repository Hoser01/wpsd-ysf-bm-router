# Third-Party Code

This project vendors selected YSF FICH decoder components from YSFBMDirect / pYSFReflector-derived code so the router can decode live WPSD YSFGateway frames.

Source inspected:

https://github.com/stefanolande/YSFBMDirect

Upstream commit:

`76f834b400af8b292e9b980742f81e4f4e738470`

Vendored files:

- `src/ysf_bm_router/vendor/pysfreflector/crc.py`
- `src/ysf_bm_router/vendor/pysfreflector/golay24128.py`
- `src/ysf_bm_router/vendor/pysfreflector/ysfconvolution.py`
- `src/ysf_bm_router/vendor/pysfreflector/ysffich.py`

The upstream repository includes the GNU GPL version 3 license. Original source headers are preserved in the vendored files. This project is licensed as `GPL-3.0-or-later`.

## WPSD / MMDVM-CM

The DMR-to-YSF conversion helper in `src/ysf_bm_router/bridge/modeconv.py` is generated from the AMBE repacking logic in WPSD/MMDVM-family `YSF2DMR/ModeConv.cpp`.

The source credits Jonathan Naylor G4KLX, Mathias Weyland HB9FRV, Andy Uribe CA6JAU, Manuel Sanchez EA7EE, AD8DP, and others, and is licensed as GPL-2.0-or-later. That license is compatible with this project's GPL-3.0-or-later licensing.
