from mp3 import MP3File


def mp3_test():
    song_path = r'E:\study\else\pydemp3\test\noid3.mp3'
    mp3 = MP3File(song_path)
    frames = mp3.read_frames(1)
    print(frames[0])

if __name__=='__main__':
    mp3_test()