# import edge_tts
# import asyncio
# import io
# import pygame

# pygame.mixer.init()

# async def text_to_speech(text: str, tts_opts=None, play_audio=True):
#     provider = (tts_opts or {}).get("provider") or "edge" 
#     try:
#         if provider == "edge":
#             voice = (tts_opts or {}).get("voice", "hi-IN-MadhurNeural")
#             rate  = (tts_opts or {}).get("rate", "+30%")
#             pitch = (tts_opts or {}).get("pitch", "-6Hz")
            

#             async def _generate_and_play():
#                 communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
                
#                 audio_bytes = bytearray()
#                 async for chunk in communicate.stream():
#                     if chunk["type"] == "audio":
#                         audio_bytes.extend(chunk["data"])
                
#                 if play_audio and audio_bytes:
#                     audio_stream = io.BytesIO(bytes(audio_bytes))
#                     pygame.mixer.music.load(audio_stream)
#                     pygame.mixer.music.play()
                    
#                     while pygame.mixer.music.get_busy():
#                         await asyncio.sleep(0.1)  
                
#                 return bytes(audio_bytes)  
            
#             audio_data = await _generate_and_play() 
            
#             return audio_data  
#     except Exception as e:
#         print(f"TTS error: {e}")
#         return None 

import edge_tts
import asyncio
import io
import pygame

pygame.mixer.init()

async def text_to_speech(text: str, tts_opts=None, play_audio=True):
    provider = (tts_opts or {}).get("provider") or "edge" 
    try:
        if provider == "edge":
            # Jarvis-like: British male voice (en-GB-RyanNeural), neutral/slightly slow rate, lower pitch for depth
            voice = (tts_opts or {}).get("voice", "en-GB-RyanNeural")
            rate  = (tts_opts or {}).get("rate", "-10%")  # Slightly slower for measured delivery
            pitch = (tts_opts or {}).get("pitch", "-15Hz")  # Lower pitch for a deeper, authoritative tone

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
                        await asyncio.sleep(0.1)  
                
                return bytes(audio_bytes)  
            
            audio_data = await _generate_and_play() 
            
            return audio_data  
    except Exception as e:
        print(f"TTS error: {e}")
        return None