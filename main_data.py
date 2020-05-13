import math
import numpy as np

from utils import sythesis_coefficients
from header import Header, ChannelModeInfo
from huffman import decode_quadruples, decode_big_values
from side_info import SideInfo, BlockTypeInfo
from utils.bit import Bit


class MainData:
    """
    The main data part of the frame consists of scalefactors, Huffman coded bits and ancillary data.
    """

    # preflag
    # This is equivalent to multiplication of the requantized scalefactors with the
    # Table 11 values which also means additional high frequency amplification
    # of the quantized values.
    # todo: check pretab. pdf为21位，和scale_band_indicies位数不匹配，个人补加末尾0
    pretab = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 3, 3, 3, 2, 0]

    scalefac_sizes = [
        (0, 0), (0, 1), (0, 2), (0, 3), (3, 0), (1, 1), (1, 2), (1, 3),
        (2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3), (4, 2), (4, 3),
    ]

    scale_band_indicies = {
        44100: {
            'L': [0, 4, 8, 12, 16, 20, 24, 30, 36, 44, 52, 62, 74, 90, 110,
                  134, 162, 196, 238, 288, 342, 418, 576],
            'S': [0, 4, 8, 12, 16, 22, 30, 40, 52, 66, 84, 106, 136, 192],
        },
        48000: {
            'L': [0, 4, 8, 12, 16, 20, 24, 30, 36, 42, 50, 60, 72, 88, 106,
                  128, 156, 190, 230, 276, 330, 384, 576],
            'S': [0, 4, 8, 12, 16, 22, 28, 38, 50, 64, 80, 100, 126, 192],
        },
        32000: {
            'L': [0, 4, 8, 12, 16, 20, 24, 30, 36, 44, 54, 66, 82, 102, 126,
                  156, 194, 240, 296, 364, 448, 550, 576],
            'S': [0, 4, 8, 12, 16, 22, 30, 42, 58, 78, 104, 138, 180, 192],
        },
    }

    def __init__(self, header: Header, side_info: SideInfo, bytes_str: str):
        self._bits = Bit(bytes_str)
        self.header = header
        self.side_info = side_info
        channel_num = 1 if header.channel_mode == ChannelModeInfo.MONO else 2

        self.unpack_scale_factors(channel_num)
        self.unpack_huffman(channel_num)
        self.requantization(channel_num)
        self.reorder()
        self.aliasing_reduction(channel_num)
        self.IMDCT(channel_num)

        # Finally we reach time domain!
        self.frequency_inversion(channel_num)
        self.synthesis(channel_num)

    def unpack_scale_factors(self, channel_num):
        """
        modified from: https://github.com/SoryRawyer/mp3po

        unpack_scale_factors : use the side information to determine how many bits
        to read for each scale factor band. the side information will also tell us
        whether or not scale factors are shared between granules for any bands
        """
        self.scalefac_l = [0] * 2
        self.scalefac_s = [0] * 2
        # i: granule; j: channel
        for gran in range(0, 2):
            granule = self.side_info.granules[gran]
            self.scalefac_l[gran] = [0] * 2
            self.scalefac_s[gran] = [0] * 2
            for chan in range(0, channel_num):
                channel = granule.channels[chan]
                slen1 = self.scalefac_sizes[channel.scalefac_compress][0]
                slen2 = self.scalefac_sizes[channel.scalefac_compress][1]
                self.scalefac_l[gran][chan] = [0] * 22
                self.scalefac_s[gran][chan] = [0] * 13
                if channel.windows_switching_flag and channel.block_type == BlockTypeInfo.THREE_SHORT_WINDOWS:
                    if channel.mixed_block_flag:
                        # mixed blocks & short blocks 17 slen1 + 18 slen2 factors
                        for k in range(0, 8):
                            self.scalefac_l[gran][chan][k] = self._bits.read_as_int_as_int(slen1)
                        for k in range(3, 6):
                            self.scalefac_s[gran][chan][k] = [0] * 3
                            for sfb in range(0, 3):
                                self.scalefac_s[gran][chan][k][sfb] = self._bits.read_as_int(slen1)
                        for k in range(6, 12):
                            self.scalefac_s[gran][chan][k] = [0] * 3
                            for sfb in range(0, 3):
                                self.scalefac_s[gran][chan][k][sfb] = self._bits.read_as_int(slen2)
                    else:
                        # just short blocks 18 slen1 + 18 slen2 factors
                        # TODO: check why origin just read 9 factors
                        # for k in range(3, 6):
                        for k in range(0, 6):
                            self.scalefac_s[gran][chan][k] = [0] * 3
                            for sfb in range(0, 3):
                                self.scalefac_s[gran][chan][k][sfb] = self._bits.read_as_int(slen1)
                        for k in range(6, 12):
                            self.scalefac_s[gran][chan][k] = [0] * 3
                            for sfb in range(0, 3):
                                self.scalefac_s[gran][chan][k][sfb] = self._bits.read_as_int(slen2)
                else:
                    # scale factors for long blocks
                    # 11 slen1 + 10 slen2 factors
                    if gran == 0:
                        for sfb in range(0, 11):
                            self.scalefac_l[gran][chan][sfb] = self._bits.read_as_int(slen1)
                        for sfb in range(11, 21):
                            self.scalefac_l[gran][chan][sfb] = self._bits.read_as_int(slen2)
                    else:
                        # reuse the scale factors from the first granule base on scifi.
                        indices = [(0, 6), (6, 11), (11, 16), (16, 21)]
                        for k in range(0, 2):
                            start, end = indices[k]
                            for sfb in range(start, end):
                                if self.side_info.scfsi[chan][k] == 1:  # reuse granule 0
                                    self.scalefac_l[gran][chan][sfb] = self.scalefac_l[gran - 1][chan][sfb]
                                else:
                                    self.scalefac_l[gran][chan][sfb] = self._bits.read_as_int(slen1)
                        for k in range(2, 4):
                            start, end = indices[k]
                            for sfb in range(start, end):
                                if self.side_info.scfsi[chan][k] == 1:  # reuse granule 0
                                    self.scalefac_l[gran][chan][sfb] = self.scalefac_l[gran - 1][chan][sfb]
                                else:
                                    self.scalefac_l[gran][chan][sfb] = self._bits.read_as_int(slen2)
                    self.scalefac_l[gran][chan][21] = 0

    def unpack_huffman(self, channel_num):
        """
        unpack_huffman : unpack the huffman samples.
        5 regions:
        - big values
        - big values
        - big values
        - count1/quadruple
        - zero

        we're assuming here that self.bits() has been put at the right location
        for us to just start reading
        """

        samples_per_granule = 576
        self.frequency_lines = [0] * 2
        for gran in range(0, 2):
            self.frequency_lines[gran] = [0] * 2
            granule = self.side_info.granules[gran]
            for chan in range(0, channel_num):
                channel = granule.channels[chan]
                self.frequency_lines[gran][chan] = [0] * 576
                # print(chan, granule)
                if channel.windows_switching_flag and channel.block_type == BlockTypeInfo.THREE_SHORT_WINDOW:
                    # mixed & short blocks
                    region_1_start = 36
                    region_2_start = samples_per_granule
                else:
                    sampling_freq = self.header.sampling_rate_frequency
                    long_bands = self.scale_band_indicies[sampling_freq]['L']
                    # print('gran chan region0: {}'.format(granule['region0_count']))
                    # print('windows_switching_flag: {}'.format(granule['windows_switching_flag']))
                    region_1_start = long_bands[channel.region0_count + 1]

                    region_2_idx = (channel.region0_count +
                                    channel.region1_count + 2)
                    print('region_2_idx: {}'.format(region_2_idx))
                    region_2_start = long_bands[region_2_idx]

                # big value regions
                early_stop = False
                for i in range(0, channel.big_values * 2, 2):
                    if self._bits.peek(1) == b'':
                        break
                    elif i >= len(self.frequency_lines[gran][chan]):
                        # If there are more Huffman code bits than necessary to decode 576 values
                        # they are regarded as stuffing bits and discarded.
                        early_stop = True
                        break
                    table_num = 0
                    if i < region_1_start:
                        table_num = channel.table_select[0]
                    elif i < region_2_start:
                        table_num = channel.table_select[1]
                    else:
                        table_num = channel.table_select[2]
                    if table_num == 0:
                        self.frequency_lines[gran][chan][i] = 0.0
                    x, y = decode_big_values(self._bits, table_num)
                    self.frequency_lines[gran][chan][i] = float(x)
                    self.frequency_lines[gran][chan][i + 1] = float(y)
                if early_stop:
                    break

                # quad region
                table_num = int(channel.count1table_select)
                # iterate until we're either out of bits or we have 576 samples
                position = channel.big_values * 2
                for i in range(channel.big_values * 2, 576, 4):
                    position = i
                    # If we're out of bits, break out!
                    if self._bits.peek(1) == b'' or i >= len(self.frequency_lines[gran][chan]) - 4:
                        break
                    v, w, x, y = decode_quadruples(self._bits, table_num)
                    self.frequency_lines[gran][chan][i] = float(v)
                    self.frequency_lines[gran][chan][i + 1] = float(w)
                    self.frequency_lines[gran][chan][i + 2] = float(x)
                    self.frequency_lines[gran][chan][i + 3] = float(y)
                position += 1
                while position < 576:
                    # remaining zero regions.
                    self.frequency_lines[gran][chan][i] = 0
                    position += 1

                # finally, unpack huffman come to the end.

    def requantization(self, channel_num):
        '''
        The decoded scaled and quantized frequency lines output from the Huffman decoder block are
        requantized using the scalefactors reconstructed in the Scalefactor decoding block together
        with some or all fields mentioned. Two equations are used depending on the window used.
        Both these equations are raised to the power of 4/3, which is the invers power used in the
        quantizer.
        '''
        self.xr = [0] * 2
        for gran in range(2):
            self.xr[gran] = [0] * 2
            for chan in range(channel_num):
                self.xr[gran][chan] = [0] * 576
                channel = self.side_info.granules[gran].channels[chan]
                scalefac_multiplier = (channel.scalefac_scale + 1) / 2
                if channel.windows_switching_flag and channel.block_type == BlockTypeInfo.THREE_SHORT_WINDOWS:
                    # short block
                    sfb_indicies = self.scale_band_indicies[self.header.sampling_rate_frequency]['S']
                    loop_idx = 0
                    for sfb in range(len(sfb_indicies) - 1):
                        for window in range(3):
                            for j in range(sfb_indicies[sfb + 1] - sfb_indicies[sfb]):
                                i = loop_idx + j
                                self.xr[gran][chan][i] = requantize_s(self.frequency_lines[gran][chan][i],
                                                                      channel.global_gain,
                                                                      channel.subblock_gain[window],
                                                                      scalefac_multiplier,
                                                                      self.scalefac_s[gran][chan][sfb][window])
                            loop_idx += sfb_indicies[sfb + 1] - sfb_indicies[sfb]

                else:
                    # long blocks
                    sfb_indicies = self.scale_band_indicies[self.header.sampling_rate_frequency]['L']
                    for sfb in range(len(sfb_indicies) - 1):
                        for i in range(sfb_indicies[sfb], sfb_indicies[sfb + 1]):
                            self.xr[gran][chan][i] = requantize_l(self.frequency_lines[gran][chan][i],
                                                                  channel.global_gain,
                                                                  scalefac_multiplier,
                                                                  self.scalefac_l[gran][chan][sfb],
                                                                  channel.preflag,
                                                                  self.pretab[sfb]
                                                                  )

    def reorder(self):
        '''
        In the MDCT block the use of long windows prior to the transformation, would generate
        frequency lines ordered first by subband and then by frequency. Using short windows instead,
        would generate frequency lines ordered first by subband, then by window and at last by frequency.

        The reordering block will search for short windows in each of the 36 subbands. If short
        windows are found they are reordered
        '''
        # TODO: reorder short blocks
        pass

    def joint_stereo_decode(self):
        '''
        The purpose of the Stereo Processing block is to perform the necessary processing to convert
        the encoded stereo signal into separate left/right stereo signals. The method used for encoding
        the stereo signal can be read from the mode and mode_extension in the header of each frame.
        '''
        if self.header.channel_mode == ChannelModeInfo.JOINT_STEREO:
            print('>>> frame used Joint stereo mode.')
            # TODO: assuming PC use big order.
            is_intensity_stereo = True if self.header.mode_extension[1] == '1' else False
            is_MS_stereo = True if self.header.mode_extension[0] == '1' else False
            if is_MS_stereo:
                print('>>> MS stereo decoding.')
                self._MS_stereo_decode()
            # TODO: check self.L R
            if is_intensity_stereo:
                print('>>> Intensity stereo decoding.')
                self._intensity_stereo_decode()
        else:
            # TODO: save result in xr.
            pass

    def _MS_stereo_decode(self):
        pass

    def _intensity_stereo_decode(self):
        pass

    def aliasing_reduction(self, channel_num):
        '''
        Aliasing reduction is done by merging the frequency lines
        using eight butterfly calculations for each sub-band.

        result save back in xr.
        '''
        # butterfly_coefficients
        c = [-0.6, -0.535, -0.33, -0.185, -0.095, -0.041, -0.00142, -0.0037]
        cs = [1 / ((1 + c_i ** 2) ** 0.5) for c_i in c]
        ca = [c_i / ((1 + c_i ** 2) ** 0.5) for c_i in c]

        for gran in range(2):
            for chan in range(channel_num):
                xar = [0] * 576
                # eight butterfly calculations for each subband
                for sb in range(32):
                    for i in range(8):
                        xar[18 * sb + 18 - i - 1] = self.xr[gran][chan][18 * sb + 18 - i - 1] * cs[i] - \
                                                    self.xr[gran][chan][18 * sb + i] * ca[i]
                        xar[18 * sb + i] = self.xr[gran][chan][18 * sb + i] + \
                                           self.xr[gran][chan][18 * sb + 18 - i - 1] * ca[i]
                    # save aliasing reduction back.
                    self.xr[gran][chan] = xar

    def IMDCT(self, channel_num):
        '''
        The frequency lines from the Alias reduction block are mapped to 32 Polyphase filter
        subbands. The IMDC will output 18 time domain samples for each of the 32 subbands.

        The first half of the block of 36 values is overlapped with the second half of the
        previous block. The second half of the actual block is stored to be used in
        the next block.
        '''
        z, pre_z = None, [0] * 18
        self.samples = [0] * 2
        for gran in range(2):
            self.samples[gran] = [0] * channel_num
            for chan in range(channel_num):
                self.samples[gran][chan] = [0] * 32
                block_type = self.side_info.granules[gran].channels[chan].block_type
                n = 12 if block_type == BlockTypeInfo.THREE_SHORT_WINDOWS else 36
                pai_factor = math.pi / (2 * n)
                # generate time-domain samples
                for sb in range(32):
                    if block_type == BlockTypeInfo.THREE_SHORT_WINDOWS:
                        # short blocks
                        x = [[0] * n for _ in range(3)]  # store time-samples
                        for window in range(3):
                            for i in range(n):
                                x[window][i] = self._generate_IMDCT_sample(i, n, pai_factor, gran, chan, sb, window)
                        z = self._window_overlaping_short_blocks(x)
                    else:
                        x = [0] * n  # store time-samples
                        for i in range(n):
                            # Producing 36 samples from 18 frequency lines
                            x[i] = self._generate_IMDCT_sample(i, n, pai_factor, gran, chan, sb)

                        # overlap windowing operation
                        if block_type == BlockTypeInfo.START:
                            z = self._window_overlaping_start_block(x)
                        elif block_type == BlockTypeInfo.END:
                            z = self._window_overlaping_end_block(x)
                        elif block_type == BlockTypeInfo.FORBIDDEN:
                            z = self._window_overlaping_long_block(x)
                        else:
                            raise Exception
                    self.samples[gran][chan][sb] = [z[i] + pre_z[i] for i in range(18)]
                    pre_z = z[18:]

    def _generate_IMDCT_sample(self, i, n, pai_factor, gran, chan, sb, window=None) -> float:
        '''
        formula:
        $x(i)=\sum_{k=0}^{(n / 2)-1} X(k) \cos \left(\frac{\pi}{2 n}\left(2 i+1+\frac{n}{2}\right)(2 k+1)\right)$

        X(k) means the k-th frequency line.
        window only be used in short blocks
        '''
        if window is not None:
            X = self.xr[gran][chan][18 * sb + window * 6:18 * (sb + 1) + (window + 1) * 6]
        else:
            X = self.xr[gran][chan][18 * sb:18 * (sb + 1)]
        x = sum([X[k] * math.cos(pai_factor * (2 * i + 1 + n / 2) * (2 * k + 1)) for k in range(n // 2)])
        return x

    def _window_overlaping_long_block(self, samples: list) -> list:
        '''
        formula:
        $z_{i}=x_{i} \sin \left(\frac{\pi}{35}\left(i+\frac{1}{2}\right)\right) \quad$ for $i=0$ to 35
        '''
        assert len(samples) == 36  # make sure samples are used for long blocks
        return [samples[i] * math.sin((i + 0.5) * math.pi / 36) for i in range(36)]

    def _window_overlaping_start_block(self, samples: list) -> list:
        '''
        formula:
        $\mathbf{z}_{i}=\left\{\begin{array}{ll}x_{i} \sin \left(\frac{\pi}{35}\left(i+\frac{1}{2}\right)\right) & \text { for } i=0 \text { to } 17 \\ x_{i} & \text { for } i=18 \text { to } 23 \\ x_{i} \sin \left(\frac{\pi}{12}\left(i-18+\frac{1}{2}\right)\right) & \text { for } i=24 \text { to } 29 \\ 0 & \text { for } i=30 \text { to } 35\end{array}\right.$
        '''
        z = [0] * 36
        for i in range(18):
            z[i] = samples[i] * math.sin((i + 0.5) * math.pi / 36)
        for i in range(18, 24):
            z[i] = samples[i]
        for i in range(24, 30):
            z[i] = samples[i] * math.sin((i - 17.5) * math.pi / 12)
        # leave rest zero.
        return z

    def _window_overlaping_end_block(self, samples: list) -> list:
        '''
        formula:
        $z_{i}=\left\{\begin{array}{ll}0 & \text { for } i=0 \text { to } 5 \\ x_{i} \sin \left(\frac{\pi}{12}\left(i-6+\frac{1}{2}\right)\right) & \text { for } i=6 \text { to } 11 \\ x_{i} & \text { for } i=12 \text { to } 17 \\ x_{i} \sin \left(\frac{\pi}{36}\left(i+\frac{1}{2}\right)\right) & \text { for } i=18 \text { to } 35\end{array}\right.$
        '''
        z = [0] * 36
        for i in range(6, 12):
            z[i] = samples[i] * math.sin((i - 5.5) * math.pi / 12)
        for i in range(12, 18):
            z[i] = samples[i]
        for i in range(18, 36):
            z[i] = samples[i] * math.sin((i + 0.5) * math.pi / 36)
        return z

    def _window_overlaping_short_blocks(self, samples_lists) -> list:
        '''
        formula:
        see pic in ~/doc/short_block_window.png
        '''
        z = [0] * 36
        y = [0] * 3
        for j in range(3):
            y[j] = [samples_lists[j][i] * math.sin((i + 0.5) * math.pi / 12) for i in range(12)]
        # leave z[0:6] zero
        for i in range(6, 12):
            z[i] = y[0][i - 6]
        for i in range(12, 18):
            z[i] = y[0][i - 6] + y[1][i - 12]
        for i in range(18, 24):
            z[i] = y[1][i - 12] + y[2][i - 18]
        for i in range(24, 30):
            z[i] = y[2][i - 18]
        # leave z[30:36] zero
        return z

    def frequency_inversion(self, channel_num):
        '''
        The output of overlap add consists of 18 time samples for each of 32
        polyphase subbands. Before processing the time samples into synthesis
        polyphase filter bank , every odd time sample of every odd subband should
        be multiplied by -1 to compensate for frequency inversion.
        '''
        for gran in range(2):
            for chan in range(channel_num):
                for sb in range(0, 32, 2):
                    # TODO: what is odd? zero base or one base
                    for idx in range(0, 18, 2):
                        self.samples[gran][chan][sb][idx] *= -1

    def synthesis(self, channel_num):
        '''
        The synthesis Polyphase filterbank transforms the 32 subbands of 18 time domain samples in
        each granule to 18 blocks of 32 PCM samples, which is the final decoding result.
        '''
        print('>>> synthesis Polyphase filterbank transforming.')
        queue_V = []
        for gran in range(2):
            for chan in range(channel_num):
                for idx in range(16):
                    # TODO: quite confused. We have 18 subbands but just use 16
                    # 1. fetch subband samples
                    X = [self.samples[gran][chan][sb][idx] for sb in range(32)]
                    # 2. DCT without optimization
                    queue_V.append(self._DCT_I(X))
                # 3. create U vector.
                U, flap = [], 0
                for idx in range(16):
                    U += queue_V[idx][flap * 32:(flap + 1) * 32]
                    flap = 1 - flap

                # 4. produce W vector
                W = [U[i] * sythesis_coefficients.D[i] for i in range(512)]

                # 5. produce PCM samples
                PCM = [sum([W[j + 32 * i] for i in range(16)]) for j in range(32)]
                # TODO: save PCM output
                # TODO: 转为整数 保存输出

    def _DCT_I(self, X: list) -> list:
        '''
        DCT-I (32-64)
        $V[i]=\sum_{k=0}^{31} X[k] \cos \left[\frac{(16+i)(2 k+1) \pi}{64}\right]$ for $i=0,1, \ldots 63$
        '''
        # V=[0]*64
        V = [sum([X[k] * math.cos((16 + i) * (2 * k + 1) * math.pi / 64) for k in range(32)]) for i in range(64)]
        return V


def requantize_s(fre_line, global_gain, subblock_gain, multiplier, scalefac_s):
    '''
    requantization for short block.
    '''
    a = (global_gain - 210 - (subblock_gain << 3)) / 4
    b = -(multiplier * scalefac_s)
    if a + b < -127:
        # too small, no need to compute.
        return 0
    else:
        xr = (fre_line ** (4 / 3)) * (2 ** (a + b))
        return xr if fre_line > 0 else -xr


def requantize_l(fre_line, global_gain, multiplier, scalefac_l, preflag, pretab):
    '''
    requantization for long block.
    '''
    c = (global_gain - 210) / 4
    d = -(multiplier * (scalefac_l + preflag * pretab))
    if c + d < -127:
        # too small, no need to compute.
        return 0
    else:
        xr = (fre_line ** (4 / 3)) * (2 ** (c + d))
        return xr if fre_line > 0 else -xr
