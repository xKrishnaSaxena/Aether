import speech_recognition as sr

r = sr.Recognizer()

with sr.Microphone() as source:
    print("Listening")
    audio_text=r.listen(source,timeout=10)
    print("Over")

    try:
        print("Text: "+r.recognize_google(audio_text))
    except:
        print("error")