import argparse
from PCM import PCM
from header import Header, ChannelModeInfo
from main_data import MainData
from side_info import SideInfo
from utils.bit import byte2str


class MP3File(object):
    """
    MP3File : look for frames and break them up into headers and data, meanwhile decoding then into PCM.
    """

    def __init__(self, mp3_file:str):
        self.filename = mp3_file
        self.position = 0
        # open file, read data into header and data frame objects
        with open(mp3_file, 'rb') as audio:
            # read audio data into a buffer. stop once we've reached the first mp3 frame
            buf = audio.read(2)
            while self._is_not_frame_start(buf[-2], buf[-1]):
                buf += audio.read(1)
            # should we save the start location of the mp3 data? Yes
            self.position = audio.tell() - 2
        # print(self.position)
        self.previous_frame_size = 0
        # keep a buffer of main data from previous frames. when we need to read main data
        # we will follow one of the following:
        #   - read all of the main data from the buffer
        #   - read the rest of the buffer, then some of the main data in the current physical frame
        #   - read the main data from immediately after the side information
        self.main_data_buffer = b''
        self.PCM_buffer = PCM()

    def read_frames(self, nframes=-1):
        """
        read n frames, save decoding PCM in PCM.buffer
        default: read all frames
        """
        frames_count = 0
        if nframes == 0:
            return
        with open(self.filename, 'rb') as audio:
            still_reading = True
            audio.seek(self.position)
            while still_reading:
                if frames_count == nframes:
                    break
                print("\n>>> Start decoding frame: %d"%frames_count)
                print('reading header starting at byte offset: {}'.format(audio.tell()))
                # Read the 4 header bytes
                buf = audio.read(4)
                bytes_str = byte2str(buf,4)
                header = Header(bytes_str)
                non_main_data_len = 4

                if header.protection == '1':
                    # TODO: CRC check
                    audio.read(2)
                    non_main_data_len += 2

                # if mono: side info is 17 bytes; else: 32
                side_info_length = 17 if header.channel_mode == ChannelModeInfo.MONO else 32
                print("channel mode: ",header.channel_mode)
                print("reading side info at byte offset: {}".format(audio.tell()))
                side_info_bytes = audio.read(side_info_length)
                bytes_str = byte2str(side_info_bytes,side_info_length)
                side_info = SideInfo(bytes_str,header.channel_mode)

                # print("side info granules: {}".format(side_info.granules))
                # print("side info main_data_begin: {}".format(side_info.main_data_begin))
                # print("side info scfsi_band: {}".format(side_info.scfsi))
                non_main_data_len += side_info_length

                main_data_length = header.frame_size - non_main_data_len # main data size in current frame
                print("reading main data at byte offset: {}\ntotal bits length: {}".format(audio.tell(),main_data_length))
                # read until the next header so we have all the main data we could possibly want

                read_bytes_count = 0
                while True:
                    new_byte = audio.peek(1)
                    if new_byte == b'':
                        still_reading = False
                        break
                    # if self.main_data_buffer == b'':
                    if read_bytes_count==0:
                        self.main_data_buffer += audio.read(2)
                        read_bytes_count+=2
                    else:
                        self.main_data_buffer += audio.read(1)
                        read_bytes_count+=1

                    if read_bytes_count >= main_data_length and not self._is_not_frame_start(self.main_data_buffer[-2], self.main_data_buffer[-1]):
                        # we've stumbled upon a new frame. return the file back to the start
                        # of the header and remove the last two bytes from the main data buffer
                        print('- read bytes: %d, find next frame, current position: %d -'%(read_bytes_count,audio.tell()-2))
                        audio.seek(audio.tell() - 2)
                        self.main_data_buffer = self.main_data_buffer[:-2]
                        break
                # At this point, we now have all the main data up until the start of the next frame

                # calculate the position at which to start reading the main data
                # then read the main data into a buffer and send that buffer somewhere
                # so that we might one day hope to know the scaling factors
                print("- main_data_begin:%-5d frame_size:%-5d main_data_length:%-5d -"
                      %(side_info.main_data_begin,header.frame_size, main_data_length))

                # main_data_bytes = self.main_data_buffer[:main_data_length]
                # self.main_data_buffer = self.main_data_buffer[main_data_length:] # remaining data would be used in next frame.

                # TODO: check data length
                this_frame_data_length = side_info.main_data_begin+main_data_length
                main_data_bytes = self.main_data_buffer[-this_frame_data_length:]
                self.main_data_buffer = self.main_data_buffer[-this_frame_data_length:]

                bytes_str = byte2str(main_data_bytes,this_frame_data_length)
                print("- main data buffer size:%d"%len(main_data_bytes))
                print("- main data length:%d" % (this_frame_data_length))
                main_data = MainData(header, side_info, bytes_str)

                if not self.PCM_buffer.is_init:
                    # provide information, e.g. sampling rate
                    # TODO: check sampling rate
                    self.PCM_buffer.set_params(main_data.channel_num,2,16000)
                self.PCM_buffer.push(main_data.pcm_output)

                frames_count+=1

            self.position = audio.tell()

    def _is_not_frame_start(self, byte1, byte2):
        '''
        header would start with FF FF or FF FB
        '''
        return (byte1 != 0xFF or (byte2 & 0xF0 != 240 and byte2 & 0xE0 != 224))

    def save_as_wav(self,filename:str):
        '''
        save decoding PCM as .wav format file
        '''
        self.PCM_buffer.flush(filename)



if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("mp3file",help="the MP3's file path")
    args = parser.parse_args()
    mp3_file=args.mp3file
    print(mp3_file)
    mp3 = MP3File(mp3_file)
    mp3.read_frames()
    mp3.save_as_wav(mp3_file[:-4]+'.wav')