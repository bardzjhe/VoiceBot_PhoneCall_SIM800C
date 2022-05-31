# Basic program to test the environment
# If the environment is well configured, which, of course, takes a lot of time 
# this program should run successfully. 
import os
from google.cloud import texttospeech

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'demoServiceAccount.json'
client = texttospeech.TextToSpeechClient()

text = "What's the matter with you. I'm gonna fly to LA next month. "

synthesis_input = texttospeech.SynthesisInput(text=text)

voice1 = texttospeech.VoiceSelectionParams(
    language_code='en-in', 
    ssml_gender=texttospeech.SsmlVoiceGender.MALE
)

# print(client.list_voices())

audio_config = texttospeech.AudioConfig(
    audio_encoding= texttospeech.AudioEncoding.MP3
)

response = client.synthesize_speech(
    input=synthesis_input,
    voice=voice1,
    audio_config=audio_config
)

with open('audio file1.mp3', 'wb') as output:
    output.write(response.audio_content)