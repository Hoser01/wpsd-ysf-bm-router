from __future__ import annotations

from dataclasses import dataclass


DMRD_PACKET_LENGTH = 55
DMR_FRAME_LENGTH = 33

DT_VOICE_LC_HEADER = 1
DT_TERMINATOR_WITH_LC = 2
DT_VOICE_SYNC = 0x10
DT_VOICE = 0x20
DMR_SYNC_DATA = 0x20
DMR_SYNC_AUDIO = 0x10


@dataclass(frozen=True)
class DmrFrame:
    sequence: int
    slot: int
    source_id: int
    destination_id: int
    repeater_id: int
    stream_id: int
    data_type: int
    voice_index: int
    flco_group: bool
    payload: bytes
    ber: int
    rssi: int

    @property
    def is_voice(self) -> bool:
        return self.data_type in {DT_VOICE_SYNC, DT_VOICE}

    @property
    def is_header(self) -> bool:
        return self.data_type == DT_VOICE_LC_HEADER

    @property
    def is_terminator(self) -> bool:
        return self.data_type == DT_TERMINATOR_WITH_LC


def parse_dmrd_packet(packet: bytes) -> DmrFrame:
    if len(packet) != DMRD_PACKET_LENGTH:
        raise ValueError(f"DMRD packet must be 55 bytes, got {len(packet)}")
    if not packet.startswith(b"DMRD"):
        raise ValueError("packet is not a DMRD frame")

    flags = packet[15]
    data_sync = bool(flags & DMR_SYNC_DATA)
    voice_sync = bool(flags & DMR_SYNC_AUDIO)
    data_type = flags & 0x0F
    voice_index = data_type
    if voice_sync:
        data_type = DT_VOICE_SYNC
        voice_index = 0
    elif not data_sync:
        data_type = DT_VOICE

    return DmrFrame(
        sequence=packet[4],
        slot=2 if flags & 0x80 else 1,
        source_id=int.from_bytes(packet[5:8], "big"),
        destination_id=int.from_bytes(packet[8:11], "big"),
        repeater_id=int.from_bytes(packet[11:15], "big"),
        stream_id=int.from_bytes(packet[16:20], "big"),
        data_type=data_type,
        voice_index=voice_index,
        flco_group=not bool(flags & 0x40),
        payload=packet[20:53],
        ber=packet[53],
        rssi=packet[54],
    )


def build_dmrd_packet(frame: DmrFrame) -> bytes:
    if len(frame.payload) != DMR_FRAME_LENGTH:
        raise ValueError(f"DMR payload must be 33 bytes, got {len(frame.payload)}")

    packet = bytearray(DMRD_PACKET_LENGTH)
    packet[0:4] = b"DMRD"
    packet[4] = frame.sequence & 0xFF
    packet[5:8] = int(frame.source_id).to_bytes(3, "big")
    packet[8:11] = int(frame.destination_id).to_bytes(3, "big")
    packet[11:15] = int(frame.repeater_id).to_bytes(4, "big")

    flags = 0x80 if frame.slot == 2 else 0x00
    if frame.data_type == DT_VOICE_SYNC:
        flags |= DMR_SYNC_AUDIO
    elif frame.data_type == DT_VOICE:
        flags |= frame.voice_index & 0x0F
    else:
        flags |= DMR_SYNC_DATA | (frame.data_type & 0x0F)
    packet[15] = flags

    packet[16:20] = int(frame.stream_id).to_bytes(4, "big")
    packet[20:53] = frame.payload
    packet[53] = frame.ber & 0xFF
    packet[54] = frame.rssi & 0xFF
    return bytes(packet)
