import json

from header import ChannelModeInfo
from utils.bit import Bit
from enum import Enum

DEBUG=True

class BlockTypeInfo(Enum):
    FORBIDDEN = '00'
    START = ' 01'
    THREE_SHORT_WINDOWS = '10'
    END = '11'


class ChanelSideInfo:
    '''
    Each header is followed by side information and contains the data needed to find where the "main data" is located.
    The main data is not located after the side information due to the varying sizes of the Huffman encoded samples.
    The side information also includes additional values that will be used in the requantization formula to reconstruct the samples into real numbers.
    '''

    def __init__(self, bits: Bit, idx: int):
        self.index = idx
        # bits = Bit(bytes_str)
        self.part2_3_length = bits.read_as_int(12)
        if DEBUG:
            print("- channel %d part2_3_length: %d"%(idx,self.part2_3_length))
        self.big_values = bits.read_as_int(9)
        self.global_gain = bits.read_as_int(8)
        self.scalefac_compress = bits.read_as_int(4)
        self.windows_switching_flag = True if bits.read() == '1' else False

        self.table_select = [0] * 3  # contain 5*2 bits or 5*3 bits
        self.subblock_gain = [0] * 3  # may not be used
        if self.windows_switching_flag:
            block_type = bits.read(2)

            for block in BlockTypeInfo:
                if block_type == block.value:
                    self.block_type = block
                    break

            self.mixed_block_flag = True if bits.read() == '1' else False  # This field is only used when windows_switching_flag is set.
            for i in range(2):
                self.table_select[i] = bits.read_as_int(5)

            if self.block_type == BlockTypeInfo.THREE_SHORT_WINDOWS:
                for i in range(3):
                    self.subblock_gain[i] = bits.read_as_int(3)
        else:
            # TODO: check whether can we just set type as '00'
            # block type doesn't given
            self.block_type=BlockTypeInfo.FORBIDDEN
            for i in range(3):
                self.table_select[i] = bits.read_as_int(5)
            self.region0_count = bits.read_as_int(4)
            self.region1_count = bits.read_as_int(3)
        self.preflag = bits.read_as_int(1)

        # The scalefactors are logarithmically quantized with a step size of 2 or v2
        self.scalefac_scale = bits.read_as_int(1)
        self.count1table_select = bits.read()

    def __str__(self):
        return json.dumps({
            'part2_3_length': self.part2_3_length,
            'big_values': self.big_values,
            'global_gain': self.global_gain,
            'scalefac_compress': self.scalefac_compress,
            'window_switch_flag': self.windows_switching_flag,
            'block_type': self.block_type,
            'mixed_block_flag': self.mixed_block_flag,
            'table_select': self.table_select,
            'region0_count': self.region0_count,
            'region1_count': self.region1_count,
            'sub_block_gain': self.subblock_gain,
            'preflag': self.preflag,
            'scalefac_scale': self.scalefac_scale,
            'count1_table_select': self.count1table_select,
        })


class Granule:
    '''
    MONO mode contain only one channel, else have two channel_num
    '''

    def __init__(self, bits: Bit, idx:int, channel_num:int):
        self.index = idx
        self.channels=[ChanelSideInfo(bits, i) for i in range(channel_num)]

    def __str__(self):
        return json.dumps({
            'index':self.index,
            'side infos':[str(info) for info in self.channels]
        })


class SideInfo:
    '''
    The side information part of the frame consists of information needed to decode the main data.
    The size depends on the encoded channel mode.
    '''

    def __init__(self, bytes_str: str, channel_mode: ChannelModeInfo):
        self._bits = Bit(bytes_str)
        self.main_data_begin = self._bits.read_as_int(9) # bit reservoir, which enables the left over free space in the main data area of a frame to be used by consecutive frames.
        if channel_mode == ChannelModeInfo.MONO:
            self.private_bits = self._bits.read_as_int(5)
        else:
            self.private_bits = self._bits.read_as_int(3)
        channel_num = 1 if channel_mode == ChannelModeInfo.MONO else 2

        # The ScaleFactor Selection Information determines weather the same scalefactors are transferred for both granules or not.
        self.scfsi = [[self._bits.read_as_int(1) for _ in range(4)] for _ in range(channel_num)]

        self.granules=[Granule(self._bits,i,channel_num) for i in range(2)]
        if DEBUG:
            total_part2_3_length=0
            for gr in range(2):
                for ch in range(2):
                    total_part2_3_length+=self.granules[gr].channels[ch].part2_3_length
            print("- total total_part2_3_length bits: %d, bytes: %.2f"%(total_part2_3_length,total_part2_3_length/8))