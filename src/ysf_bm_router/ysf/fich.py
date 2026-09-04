from __future__ import annotations

from dataclasses import dataclass

from ysf_bm_router.vendor.pysfreflector import ysffich, ysfpayload


class YsfDecodeError(ValueError):
    """Raised when a YSF frame cannot be decoded safely."""


@dataclass(frozen=True)
class Fich:
    dgid: int
    information_type: int | None = None
    communication_mode: int | None = None
    frame_total: int | None = None
    data_type: int | None = None
    frame_number: int | None = None
    voip: bool | None = None
    sql_open: bool | None = None
    raw: bytes = b""


YSFD_FICH_OFFSET = 40
YSF_SYNC = b"\xD4\x71\xC9\x63\x4D"


@dataclass(frozen=True)
class YsfFrame:
    source: str
    gateway: str
    destination: str
    frame_number: int
    fich: Fich
    raw: bytes


def decode_dgid_from_fich_bytes(fich: bytes) -> int:
    if len(fich) < 25:
        raise YsfDecodeError(f"FICH data is too short: {len(fich)} bytes")

    decoded = ysffich.decode(fich)
    if not decoded:
        raise YsfDecodeError("FICH CRC check failed")

    dgid = ysffich.getSQ()
    if not 0 <= dgid <= 99 and dgid != 127:
        raise YsfDecodeError(f"Decoded DG-ID is outside expected range: {dgid}")
    return dgid


def decode_fich(fich: bytes) -> Fich:
    if len(fich) < 25:
        raise YsfDecodeError(f"FICH data is too short: {len(fich)} bytes")

    decoded = ysffich.decode(fich)
    if not decoded:
        raise YsfDecodeError("FICH CRC check failed")

    return Fich(
        dgid=ysffich.getSQ(),
        information_type=ysffich.getFI(),
        communication_mode=ysffich.getCM(),
        frame_total=ysffich.getFT(),
        data_type=ysffich.getDT(),
        frame_number=ysffich.getFN(),
        voip=ysffich.getVoIP(),
        sql_open=ysffich.getSQL(),
        raw=bytes(decoded),
    )


def parse_ysfd_frame(data: bytes) -> YsfFrame:
    if not data.startswith(b"YSFD"):
        raise YsfDecodeError("Packet is not a YSFD frame")
    if len(data) < YSFD_FICH_OFFSET + 25:
        raise YsfDecodeError(f"YSFD frame is too short: {len(data)} bytes")

    return YsfFrame(
        source=decode_ascii_field(data[4:14]),
        gateway=decode_ascii_field(data[14:24]),
        destination=decode_ascii_field(data[24:34]),
        frame_number=data[34],
        fich=decode_fich(data[YSFD_FICH_OFFSET:]),
        raw=data,
    )


def rewrite_ysfd_dgid(data: bytes, dgid: int) -> bytes:
    if not data.startswith(b"YSFD"):
        return data
    if len(data) < YSFD_FICH_OFFSET + 25:
        raise YsfDecodeError(f"YSFD frame is too short: {len(data)} bytes")
    if not 0 <= dgid <= 99 and dgid != 127:
        raise YsfDecodeError(f"DG-ID is outside expected range: {dgid}")

    packet = bytearray(data)
    decoded = ysffich.decode(packet[YSFD_FICH_OFFSET:])
    if not decoded:
        raise YsfDecodeError("FICH CRC check failed")

    ysffich.setSQ(dgid)
    ysffich.encode(packet)
    return bytes(packet)


def rewrite_ysfd_for_mmdvm(data: bytes, dgid: int) -> bytes:
    if not data.startswith(b"YSFD"):
        return data
    if len(data) < YSFD_FICH_OFFSET + 25:
        raise YsfDecodeError(f"YSFD frame is too short: {len(data)} bytes")
    if not 0 <= dgid <= 99 and dgid != 127:
        raise YsfDecodeError(f"DG-ID is outside expected range: {dgid}")

    packet = bytearray(data)
    decoded = ysffich.decode(packet[YSFD_FICH_OFFSET:])
    if not decoded:
        raise YsfDecodeError("FICH CRC check failed")

    ysffich.setSQ(dgid)
    ysffich.setVoIP(False)
    ysffich.encode(packet)
    return bytes(packet)


def rewrite_ysfd_source_field(data: bytes, source: str) -> bytes:
    if not data.startswith(b"YSFD"):
        return data
    if len(data) < 14:
        raise YsfDecodeError(f"YSFD frame is too short: {len(data)} bytes")

    packet = bytearray(data)
    packet[4:14] = source[:10].ljust(10).encode("ascii", errors="replace")
    return bytes(packet)


def rewrite_ysfd_vd2_source(data: bytes, source: str) -> bytes:
    if not data.startswith(b"YSFD"):
        return data
    if len(data) < 155:
        raise YsfDecodeError(f"YSFD frame is too short: {len(data)} bytes")

    frame = parse_ysfd_frame(data)
    if frame.fich.frame_number != 1 or frame.fich.data_type != 2:
        return data

    encoded_source = source[:10].ljust(10).encode("ascii", errors="replace")
    payload = bytearray(data[35:])
    ysfpayload.writeVDMmode2Data(payload, encoded_source)
    return data[:35] + bytes(payload)


def make_ysfd_header_frame(
    template: bytes | None,
    dgid: int,
    network_source: str,
    source: str,
    destination: str = "ALL",
    communication_mode: int = 0,
    ysf_radio_id: str = "*****",
) -> bytes:
    if not 0 <= dgid <= 99 and dgid != 127:
        raise YsfDecodeError(f"DG-ID is outside expected range: {dgid}")

    if template is None:
        packet = bytearray(155)
        packet[0:4] = b"YSFD"
        packet[35:40] = YSF_SYNC
        ysffich.m_fich = [0, 0, 0, 0, 0, 0]
    else:
        if not template.startswith(b"YSFD"):
            raise YsfDecodeError("Packet is not a YSFD frame")
        if len(template) < 155:
            raise YsfDecodeError(f"YSFD frame is too short: {len(template)} bytes")
        packet = bytearray(template)
        decoded = ysffich.decode(packet[YSFD_FICH_OFFSET:])
        if not decoded:
            raise YsfDecodeError("FICH CRC check failed")

    packet[4:14] = encode_ascii_field(network_source)
    packet[14:24] = encode_ascii_field(source)
    packet[24:34] = encode_ascii_field(destination)
    packet[34] = 0

    ysffich.setFI(0)
    ysffich.setCS(2)
    ysffich.setCM(communication_mode)
    ysffich.setBN(0)
    ysffich.setBT(0)
    ysffich.setFN(0)
    ysffich.setFT(7)
    ysffich.setDev(False)
    ysffich.setMR(0)
    ysffich.setVoIP(False)
    ysffich.setDT(2)
    ysffich.setSQL(False)
    ysffich.setSQ(dgid)
    ysffich.encode(packet)

    payload = bytearray(packet[35:])
    csd1 = b"*****" + ysf_radio_id[:5].ljust(5).encode("ascii", errors="replace")
    csd1 += source[:10].ljust(10).encode("ascii", errors="replace")
    csd2 = b" " * 20
    ysfpayload.writeHeader(payload, csd1, csd2)
    packet[35:] = payload
    return bytes(packet)


def make_ysfd_terminator_frame(
    dgid: int,
    network_source: str,
    source: str,
    destination: str = "ALL",
    sequence: int = 0,
    communication_mode: int = 0,
) -> bytes:
    if not 0 <= dgid <= 99 and dgid != 127:
        raise YsfDecodeError(f"DG-ID is outside expected range: {dgid}")

    packet = bytearray(155)
    packet[0:4] = b"YSFD"
    packet[4:14] = encode_ascii_field(network_source)
    packet[14:24] = encode_ascii_field(source)
    packet[24:34] = encode_ascii_field(destination)
    packet[34] = (sequence & 0x7F) << 1
    packet[35:40] = YSF_SYNC

    ysffich.m_fich = [0, 0, 0, 0, 0, 0]
    ysffich.setFI(2)
    ysffich.setCS(2)
    ysffich.setCM(communication_mode)
    ysffich.setBN(0)
    ysffich.setBT(0)
    ysffich.setFN(0)
    ysffich.setFT(7)
    ysffich.setDev(False)
    ysffich.setMR(0)
    ysffich.setVoIP(False)
    ysffich.setDT(2)
    ysffich.setSQL(False)
    ysffich.setSQ(dgid)
    ysffich.encode(packet)
    return bytes(packet)


def make_ysfd_vd2_data_frame(
    vch_chunks: list[bytes],
    dgid: int,
    network_source: str,
    source: str,
    destination: str = "ALL",
    sequence: int = 0,
    frame_number: int = 0,
    frame_total: int = 7,
    data_channel: bytes = b"          ",
    communication_mode: int = 0,
) -> bytes:
    if len(vch_chunks) != 5:
        raise YsfDecodeError(f"YSF VD mode 2 data frame needs 5 VCH chunks, got {len(vch_chunks)}")
    for chunk in vch_chunks:
        if len(chunk) != 13:
            raise YsfDecodeError(f"YSF VCH chunk must be 13 bytes, got {len(chunk)}")
    if not 0 <= dgid <= 99 and dgid != 127:
        raise YsfDecodeError(f"DG-ID is outside expected range: {dgid}")

    packet = bytearray(155)
    packet[0:4] = b"YSFD"
    packet[4:14] = encode_ascii_field(network_source)
    packet[14:24] = encode_ascii_field(source)
    packet[24:34] = encode_ascii_field(destination)
    packet[34] = (sequence & 0x7F) << 1
    packet[35:40] = YSF_SYNC

    payload = bytearray(packet[35:])
    ysfpayload.writeVDMmode2Data(payload, data_channel[:10].ljust(10, b" "))
    for index, chunk in enumerate(vch_chunks):
        start = 35 + (index * 18)
        payload[start : start + 13] = chunk
    packet[35:] = payload

    ysffich.m_fich = [0, 0, 0, 0, 0, 0]
    ysffich.setFI(1)
    ysffich.setCS(2)
    ysffich.setCM(communication_mode)
    ysffich.setBN(0)
    ysffich.setBT(0)
    ysffich.setFN(frame_number)
    ysffich.setFT(frame_total)
    ysffich.setDev(False)
    ysffich.setMR(0)
    ysffich.setVoIP(False)
    ysffich.setDT(2)
    ysffich.setSQL(False)
    ysffich.setSQ(dgid)
    ysffich.encode(packet)
    return bytes(packet)


def encode_ascii_field(value: str) -> bytes:
    return value[:10].ljust(10).encode("ascii", errors="replace")


def decode_ascii_field(value: bytes) -> str:
    return value.rstrip(b" \x00").decode("ascii", errors="replace")
