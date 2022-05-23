"First pip install pygame"

from pygame import mixer
import time

mixer.init()
mixer.music.load('01.mp3')
mixer.music.play()
time.sleep(20)
mixer.music.stop()