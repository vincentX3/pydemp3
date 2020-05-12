from header import ChannelModeInfo
from side_info import SideInfo
from pprint import pprint

expected_result={
    'main_data_begin':0,
    'private_bits':0,
    'scfsi':[['1', '1', '1', '1'], ['0', '1', '1', '1']],
    'part2_3_length':806,
    'big_values':83,
    'global_gain':110,
    'scalefac_compress':0,
    'windows_switching_flag':False,
    'table_select':[1,1,3],
    'subblock_gain':[0,0,0],
    'region0_count':4,
    'region1_count':6,
    'preflag':False,
    'scalefac_scale':'0',
    'count1table_select':'1'

}

def sideinfo_test():
    # dual channel
    num_bytes = 32
    raw ='00 0F 73 26 29 B7 00 21 1A 62 31 E0 17 40 00 00 00 0A B1 60 F2 01 84 6D C8 F4 00 5E D4 00 88 00'
    raw = ''.join(raw.split(' '))
    print(raw)
    bytes_str = bin(int(raw,16))[2:]
    bytes_str = '0'*(num_bytes*8-len(bytes_str))+bytes_str
    side_info = SideInfo(bytes_str,ChannelModeInfo.JOINT_STEREO)
    pprint(vars(side_info))
    pprint(vars(side_info.granules[0].channels[0]))
    pprint(vars(side_info.granules[0].channels[1]))
    # pprint(vars(side_info.granules[1]))

    assert side_info.main_data_begin==expected_result['main_data_begin']
    assert side_info.scfsi==expected_result['scfsi']
    assert side_info.private_bits==expected_result['private_bits']

    channel = side_info.granules[0].channels[0]
    assert channel.part2_3_length==expected_result['part2_3_length']
    assert channel.big_values==expected_result['big_values']
    assert channel.global_gain==expected_result['global_gain']
    assert channel.scalefac_compress==expected_result['scalefac_compress']
    assert channel.windows_switching_flag==expected_result['windows_switching_flag']
    assert channel.table_select==expected_result['table_select']
    assert channel.subblock_gain==expected_result['subblock_gain']
    assert channel.region0_count==expected_result['region0_count']
    assert channel.region1_count==expected_result['region1_count']
    assert channel.preflag==expected_result['preflag']
    assert channel.scalefac_scale==expected_result['scalefac_scale']
    assert channel.count1table_select==expected_result['count1table_select']


if __name__=='__main__':
    sideinfo_test()