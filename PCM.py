import wave


class PCM:
    '''
    class contains decoded raw PCM and relevant information which helps to covert PCM into .wav file.
    '''

    def __init__(self):
        self.buffer = b''
        self.nchannels = 1
        self.sampwidth = 2  # bytes
        self.framerate = 16000  # sampling rate
        self.nframes = 0
        self.is_init = False

    def set_params(self, nchannels, sampwidth, framerate):
        self.nchannels = nchannels
        self.sampwidth = sampwidth
        self.framerate = framerate

    def push(self, samples: list):
        '''
        save samples into buffer
        samples: list which contains float type samples.
        '''
        for sample in samples:
            self.buffer+=float2bytes(sample)

    def flush(self, wavfile, write_mode='wb'):
        '''
        flush buffer data into a .wav file, and empty the buffer.
        '''
        print(">>> save decoding result: %s"%wavfile)
        if len(self.buffer) == 0:
            raise EmptyBufferError
        with wave.open(wavfile, 'wb') as wav:
            wav.setparams((self.nchannels, self.sampwidth,
                           self.framerate, 0, 'NONE', 'NONE'))
            wav.writeframes(self.buffer)
        self.buffer = b''


def float2bytes(value: float, bytes_length=2, byteorder='big') -> bytes:
    if bytes_length == 2:
        if value > 32767:
            value = 32767
        elif value < -32768:
            value = -32768
    elif bytes_length == 2:
        if value > 127:
            value = 127
        elif value < -128:
            value = -128
    return int(value).to_bytes(bytes_length, byteorder=byteorder, signed=True)


class EmptyBufferError(Exception):
    pass
