from header import Header, MPEGAudioVersionInfo, LayerInfo, ChannelModeInfo
from pprint import pprint


def header_test():
    raw_header = 'FFFB9064'
    bytes_str = bin(int(raw_header,16))[2:]
    print(bytes_str)
    header = Header(bytes_str)
    # pprint(vars(header))
    print(header)

    assert header.frame_sync=='11111111111'
    assert header.MPEG_version==MPEGAudioVersionInfo.ONE
    assert header.layer==LayerInfo.III
    assert header.bitrate==128000
    assert header.sampling_rate_frequency==44100
    assert header.channel_mode==ChannelModeInfo.JOINT_STEREO


header_test()