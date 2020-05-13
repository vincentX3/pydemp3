import json
from enum import Enum, unique
from pprint import pprint

from utils.bit import Bit


@unique
class MPEGAudioVersionInfo(Enum):
    TWO_POINT_FIVE = '00'
    RESERVED = '01'
    TWO = '10'
    ONE = '11'


@unique
class LayerInfo(Enum):
    RESERVED = '00'
    III = '01'
    II = '10'
    I = '11'


@unique
class ChannelModeInfo(Enum):
    STEREO = '00'
    JOINT_STEREO = '01'
    DUAL_CHANNEL = '10'
    MONO = '11'


class InvalidEncodingError(Exception):
    """
    raise error when encounter bad encoding.
    """
    pass


class Header(object):
    """
    reference: http://www.mp3-tech.org/programmer/frame_header.html
    The frame header itself is 32 bits (4 bytes) length.Frames may also feature an optional CRC checksum. It is 16 bits long.
    the details of what is within a frame header:
        AAAAAAAA AAABBCCD EEEEFFGH IIJJKLMM

    Sign	Length(bits)	Position (bits)	Description
    A	    11          	(31-21)	Frame sync
    B	    2	            (20,19)	MPEG Audio version ID
                                    00 - MPEG Version 2.5 (later extension of MPEG 2)
                                    01 - reserved
                                    10 - MPEG Version 2 (ISO/IEC 13818-3)
                                    11 - MPEG Version 1 (ISO/IEC 11172-3)
    C	    2	            (18,17)	Layer description
                                    00 - reserved
                                    01 - Layer III
                                    10 - Layer II
                                    11 - Layer I
    D	    1	            (16)	Protection bit
    E	    4	            (15,12)	Bitrate index
    F	    2	            (11,10)	Sampling rate frequency index
    G	    1	            (9)	    Padding bit
    H	    1	            (8)	    Private bit. This one is only informative.
    I	    2	            (7,6)	Channel Mode
                                    00 - Stereo
                                    01 - Joint stereo (Stereo)
                                    10 - Dual channel (2 mono channel_num)
                                    11 - Single channel (Mono)
    J	    2	            (5,4)	Mode extension (Only used in Joint stereo)
    K	    1	            (3)	    Copyright
    L	    1	            (2)	    Original
    M	    2	            (1,0)	Emphasis
                                    00 - none
                                    01 - 50/15 ms
                                    10 - reserved
                                    11 - CCIT J.17
    """

    bitrate_table_V1 = {
        # V1 MPEG Version 1
        LayerInfo.I: {
            '0001': 32000,
            '0010': 64000,
            '0011': 96000,
            '0100': 128000,
            '0101': 160000,
            '0110': 192000,
            '0111': 224000,
            '1000': 256000,
            '1001': 288000,
            '1010': 320000,
            '1011': 352000,
            '1100': 384000,
            '1101': 416000,
            '1110': 448000,
        },
        LayerInfo.II: {
            '0001': 32000,
            '0010': 48000,
            '0011': 56000,
            '0100': 64000,
            '0101': 80000,
            '0110': 96000,
            '0111': 112000,
            '1000': 128000,
            '1001': 160000,
            '1010': 192000,
            '1011': 224000,
            '1100': 256000,
            '1101': 320000,
            '1110': 384000,
        },
        LayerInfo.III: {
            '0001': 32000,
            '0010': 40000,
            '0011': 48000,
            '0100': 56000,
            '0101': 64000,
            '0110': 80000,
            '0111': 96000,
            '1000': 112000,
            '1001': 128000,
            '1010': 160000,
            '1011': 192000,
            '1100': 224000,
            '1101': 256000,
            '1110': 320000,
        }
    }

    sampling_rate_frequency_table = {
        MPEGAudioVersionInfo.ONE: {
            '00': 44100,
            '01': 48000,
            '10': 32000,
        },
        MPEGAudioVersionInfo.TWO: {
            '00': 22050,
            '01': 24000,
            '10': 16000,
        },
        MPEGAudioVersionInfo.TWO_POINT_FIVE: {
            '00': 11025,
            '01': 12000,
            '10': 8000,
        },
    }

    padding_table = {
        LayerInfo.I: 4,
        LayerInfo.II: 1,
        LayerInfo.III: 1,
    }

    '''
    The emphasis indication is here to tell the decoder that the file must be de-emphasized, 
    ie the decoder must 're-equalize' the sound after a Dolby-like noise supression. It is rarely used.
    '''
    emphasis_table = {
        "00": "none",
        "01": "50 / 15 ms",
        "10": "reserved",
        "11": "CCIT J.17"
    }

    def __init__(self, bytes_str:str):
        self._bits = Bit(bytes_str)
        self.frame_sync = self._bits.read(11)
        version = self._bits.read(2)

        valid_encode = False
        for ver in MPEGAudioVersionInfo:
            if ver.value == version:
                self.MPEG_version = ver
                valid_encode = True
                break
        if not valid_encode:
            raise InvalidEncodingError

        valid_encode = False
        layer = self._bits.read(2)
        for lay in LayerInfo:
            if lay.value == layer:
                self.layer = lay
                valid_encode = True
                break
        if not valid_encode:
            raise InvalidEncodingError

        self.protection = self._bits.read()
        bitrate = self._bits.read(4)
        self.bitrate = self.bitrate_table_V1[self.layer][bitrate]
        frequency = self._bits.read(2)
        self.sampling_rate_frequency = self.sampling_rate_frequency_table[self.MPEG_version][frequency]
        self.padding = self._bits.read()
        self.private = self._bits.read()  # Private bit. This one is only informative.

        valid_encode = False
        mode = self._bits.read(2)
        for channel in ChannelModeInfo:
            if channel.value == mode:
                self.channel_mode = channel
                valid_encode = True
                break
        if not valid_encode:
            raise InvalidEncodingError

        # TODO: support mode extension (Only used in Joint stereo)
        self.mode_extension = self._bits.read(2)
        right = self._bits.read()
        self.copyright = True if right == '1' else False
        ori = self._bits.read()
        self.original = True if ori == '1' else False
        emphasis = self._bits.read(2)
        self.emphasis = self.emphasis_table[emphasis]

        # calculate the frame size in bytes
        self.frame_size = int(144 * (self.bitrate / self.sampling_rate_frequency)
                              + (int(self.padding, 2) * self.padding_table[self.layer]))

    def __str__(self):
        return json.dumps({
            'version':self.MPEG_version.value,
            'channel mode':self.channel_mode.value,
            'layer mode':self.layer.value,
            'sampling rate frequency':self.sampling_rate_frequency,
            'bitrate':self.bitrate,
            'mode extension':self.mode_extension
        })