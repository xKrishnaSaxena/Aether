import edge_tts
import asyncio
import io
import pygame

pygame.mixer.init()

def text_to_speech(text: str, tts_opts=None, play_audio=True):
    provider = (tts_opts or {}).get("provider") or "edge" 
    try:
        if provider == "edge":
            voice = (tts_opts or {}).get("voice", "hi-IN-MadhurNeural")
            rate  = (tts_opts or {}).get("rate", "+50%")
            pitch = (tts_opts or {}).get("pitch", "-6Hz")
            
            async def _generate_and_play():
                communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
                
                audio_bytes = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes.extend(chunk["data"])
                
                if play_audio and audio_bytes:
                    audio_stream = io.BytesIO(bytes(audio_bytes))
                    pygame.mixer.music.load(audio_stream)
                    pygame.mixer.music.play()
                    

                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(100)
                
                return bytes(audio_bytes)  
            
            audio_data = asyncio.run(_generate_and_play())
            
            if play_audio:
                print("Audio playback completed.")
            
            return audio_data  
    except Exception as e:
        print(f"TTS error: {e}")
        return None

text_to_speech("""
You can change the rate, volume and pitch of the generated speech by using the --rate, --volume and --pitch options. When using a negative value, you will need to use --[option]=-50% instead of --[option] -50% to avoid the option being interpreted as a command line option.
""", play_audio=True)

