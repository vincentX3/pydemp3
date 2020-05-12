class Bit:
    '''
    basic manipulation for bits
    '''

    def __init__(self, bits='', pointer=0):
        self.__bits = bits
        self.__pointer = pointer

    def peek(self, num=1):
        if not self._check_valid_index(self.__pointer + num - 1):
            raise IndexError("invalid number of bits to peek.")
        return self.__bits[self.__pointer:self.__pointer + num]

    def read(self, num=1):
        if not self._check_valid_index(self.__pointer + num - 1):
            raise IndexError("invalid number of bits to read.")
        bits = self.__bits[self.__pointer:self.__pointer + num]
        self.__pointer += num
        return bits

    def read_all(self):
        return self.__bits[self.__pointer:]

    def read_as_int(self, num: int) -> int:
        '''
        read a number of bits and translate into 10-based integer.
        '''
        tmp = self.read(num)
        return 0 if tmp==b'' else int(tmp, 2)

    def add_bits(self, bits: str, pos=None):
        if pos is None:
            pos = self.__pointer
        else:
            if not self._check_valid_index(pos):
                raise IndexError
        self.__bits = self.__bits[:self.__pointer + 1] + bits + self.__bits[self.__pointer + 1:]

    def _check_valid_index(self, idx):
        return idx < len(self.__bits)

    def get_pointer(self):
        return self.__pointer

    def set_pointer(self, idx):
        if not self._check_valid_index(idx):
            raise IndexError
        self.__pointer = idx


def byte2str(byte: bytes, num: int, byteorder='big') -> str:
    '''
    convert raw bytes to equivalent binary expression str.
    '''
    bytes_str = bin(int.from_bytes(byte, byteorder=byteorder, signed=False))[2:]
    bytes_str = '0' * (num * 8 - len(bytes_str)) + bytes_str
    return bytes_str


if __name__ == '__main__':
    # test
    raw_bits = '1001'
    bits = Bit(raw_bits)
    print(bits.peek())
    print(bits.read(3))
    print(bits.get_pointer())
    bits.add_bits('110')
    bits.set_pointer(0)
    print(bits.read_all())
