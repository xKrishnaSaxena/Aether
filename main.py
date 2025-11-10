# import os
# from dotenv import load_dotenv
# import speech_recognition as sr
# from langgraph.graph import StateGraph,END
# from langchain_core.messages import AIMessage,HumanMessage
# from langchain_community.tools import DuckDuckGoSearchResults
# from state import State
# from voice_module import text_to_speech as speak
# load_dotenv()

# DOC_FOLDER=os.path.expanduser("~/aether_docs")
# os.makedirs(DOC_FOLDER,exist_ok=True)

# recognizer=sr.Recognizer()
# mic=sr.Microphone() 
# search_results_tool=DuckDuckGoSearchResults(num_results=5)

# async def listen_node(state:State)-> State:
#     print("Listening boss.. (Say 'exit' to quit)")
#     state["user_input"]=""
#     try:
#         with mic as source:
#             recognizer.adjust_for_ambient_noise(source,duration=1)
#             audio=recognizer.listen(source,timeout=10,phrase_time_limit=10)
#         text=recognizer.recognize_google(audio).lower()
#         print(f"You Said : {text}")
#         state["user_input"]=text
#         if text == "exit":
#             return {**state , "messages":state["messages"]+[AIMessage(content="Goodbye!")]}
#     except sr.UnknownValueError:
#         print("Sorry, didn't catch that. Typing fallback:")
#     except (sr.RequestError, sr.WaitTimeoutError):
#         print("Mic/STT issue; using text input.")
#     except Exception as e:
#         print(f"Listen error: {e}; using text input.")

#     return state

# async def search_node(state:State) -> State:
    

# def end_turn_node(state: State) -> State:
#     state["search_results"] = {}
#     state["decision"] = ""
#     state["user_input"] = ""
#     state["topic"] = ""
#     state["route_action"] = ""
#     return state


# graph=StateGraph(State)
# # Listen Node
# graph.add_node("listen",listen_node)
# graph.add_edge("listen",END)
# # Search Node
# # Parse Search Results
# # Humour maybe
# # TTS
# # END
# graph.set_entry_point("listen")
# app = graph.compile()

# async def main():
#     initial_state = {"messages": [], "user_input": "", "search_results": {}, "decision": "", "topic": "", "route_action": ""}
#     while True:
#         try:
#             await speak("Welcome boss")
#             res=await app.ainvoke(initial_state)
#             if "goodbye" in str(res).lower() or "exit" in res.get("user_input", ""):
#                 await speak("Goodbye boss")
#                 break
#             initial_state = end_turn_node(res)
#         except KeyboardInterrupt:
#             await speak("Shutting down.")
#             break
#         except Exception as e:
#             print(f"Loop error: {e}")
#             initial_state = end_turn_node(initial_state)
#             await speak("Error occurred; continuing.")

# import asyncio
# if __name__ == "__main__":
#     asyncio.run(main())



import os
import json  # Added for parsing search results
from dotenv import load_dotenv
import speech_recognition as sr
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.tools import DuckDuckGoSearchResults
from state import State
from voice_module import text_to_speech as speak
import re  # For simple free parsing with regex

load_dotenv()

DOC_FOLDER = os.path.expanduser("~/aether_docs")
os.makedirs(DOC_FOLDER, exist_ok=True)

recognizer = sr.Recognizer()
mic = sr.Microphone()
search_results_tool = DuckDuckGoSearchResults(num_results=5)


async def listen_node(state: State) -> State:
    print("Listening boss.. (Say 'exit' to quit)")
    state["user_input"] = ""
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
        text = recognizer.recognize_google(audio).lower()
        print(f"You Said: {text}")
        state["user_input"] = text
        if "exit" in text:
            state["route_action"] = "exit"
            return state
    except sr.UnknownValueError:
        print("Sorry, didn't catch that. Typing fallback:")
        # Fallback to text input if needed, but for now, proceed with empty
    except (sr.RequestError, sr.WaitTimeoutError):
        print("Mic/STT issue; using text input.")
    except Exception as e:
        print(f"Listen error: {e}; using text input.")

    state["route_action"] = "search"
    return state


def should_route(state: State):
    """Conditional routing after listen."""
    if state["route_action"] == "exit":
        return END
    return "search"


async def search_node(state: State) -> State:
    query = state["user_input"].strip()
    if not query:
        state["search_results"] = []
        state["parsed_output"] = "No query provided, boss. Try again!"
        state["route_action"] = "tts"  # Skip to TTS for feedback
        return state

    try:
        # Use .run() for string output
        results_str = search_results_tool.run(query)
        print(f"Raw search response: {results_str[:200]}...")  # Debug print (remove if not needed)
        
        if not results_str or not results_str.strip():
            raise ValueError("Empty search response")
            
        # Treat as string full text since not JSON
        state["full_text"] = results_str
        state["search_results"] = []  # No list
        state["topic"] = query  # Simple topic extraction as the query itself
    except (ValueError, Exception) as e:
        print(f"Search error: {e}")
        state["search_results"] = []
        state["full_text"] = ""
        state["parsed_output"] = "Search came up empty, sir. The web's being shy today."
        state["route_action"] = "tts"
    else:
        state["route_action"] = "parse"

    return state


async def parse_node(state: State) -> State:
    """Free parsing: Extract and summarize snippets using string methods and regex (no APIs)."""
    full_text = state.get("full_text", "")
    results = state.get("search_results", [])
    
    if not full_text and not results:
        state["parsed_output"] = "No search results found."
        state["route_action"] = "humor"  # Still add humor if possible
        return state

    try:
        if full_text:
            # Use the raw string directly
            snippets = [full_text]  # Treat whole as one snippet
        else:
            # Fallback for list format
            snippets = [r.get('snippet', r.get('body', r.get('text', ''))) for r in results if r and r.get('snippet') or r.get('body') or r.get('text')]
        
        if not snippets:
            state["parsed_output"] = "No relevant text found in results."
            state["route_action"] = "humor"
            return state

        # Concatenate snippets
        full_text = ' '.join(snippets)

        # Simple free parsing: Split into sentences, filter non-empty, take top 3-4 for summary
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', full_text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s) > 10]  # Filter short/irrelevant

        # Crude summary: Join top sentences
        summary = ' '.join(sentences[:4])
        if len(summary) > 200:
            summary = summary[:200] + "..."  # Truncate for brevity

        # Extract key phrases (simple regex for nouns/phrases)
        key_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[a-z]+){0,3}\b', summary)
        if key_phrases:
            summary += f" Key points: {', '.join(set(key_phrases[:5]))}."  # Dedup and add

        state["parsed_output"] = summary
    except Exception as e:
        print(f"Parse error: {e}")
        state["parsed_output"] = "Parsing failed, but search worked. Raw info available if needed."
    
    state["route_action"] = "humor"
    return state


async def humor_node(state: State) -> State:
    """Add Jarvis-like humor: Predefined witty responses based on topic keywords (free, no API)."""
    topic = state["topic"].lower()
    parsed = state.get("parsed_output", "No summary to witty about.")

    # Simple keyword-based humor dictionary (expand as needed)
    humor_lines = {
        "weather": "Sounds like a perfect day to stay inside and plot world domination, sir.",
        "news": "Ah, the news. Where facts go to get twisted like a pretzel at a yoga class.",
        "joke": "Why did the computer go to therapy? It had too many bytes of emotional baggage!",
        "python": "Python? The snake or the code? Either way, it's slithering ahead in popularity, boss.",
        "default": "Fascinating data, boss. If only humans came with a 'search' button."
    }

    # Detect rough category
    if any(word in topic for word in ["weather", "rain", "sun"]):
        humor = humor_lines["weather"]
    elif any(word in topic for word in ["news", "politics", "current"]):
        humor = humor_lines["news"]
    elif "joke" in topic or "funny" in topic:
        humor = humor_lines["joke"]
    elif "python" in topic:
        humor = humor_lines["python"]
    else:
        humor = humor_lines["default"]

    state["response"] = f"{parsed} {humor}"
    state["route_action"] = "tts"
    return state


async def tts_node(state: State) -> State:
    """TTS the final parsed + humor response."""
    response = state.get("response", state.get("parsed_output", "Nothing to say, sir."))
    await speak(response)
    print(f"TTS Output: {response}")
    return state


def end_turn_node(state: State) -> State:
    # Use .get() to avoid KeyError if keys missing
    state["search_results"] = state.get("search_results", {})
    state["decision"] = state.get("decision", "")
    state["user_input"] = state.get("user_input", "")
    state["topic"] = state.get("topic", "")
    state["route_action"] = state.get("route_action", "")
    state["parsed_output"] = state.get("parsed_output", "")
    state["response"] = state.get("response", "")
    state["full_text"] = state.get("full_text", "")  # Clear new key
    # Clear them
    state["search_results"] = {}
    state["decision"] = ""
    state["user_input"] = ""
    state["topic"] = ""
    state["route_action"] = ""
    state["parsed_output"] = ""
    state["response"] = ""
    state["full_text"] = ""
    return state


# Build the graph
graph = StateGraph(State)

# Add nodes
graph.add_node("listen", listen_node)
graph.add_node("search", search_node)
graph.add_node("parse", parse_node)
graph.add_node("humor", humor_node)
graph.add_node("tts", tts_node)

# Edges
graph.set_entry_point("listen")
graph.add_conditional_edges(
    "listen",
    should_route,
    {
        "search": "search",
        END: END
    }
)
graph.add_conditional_edges(
    "search",
    lambda s: s["route_action"],
    {
        "parse": "parse",
        "tts": "tts"  # Direct to TTS if error
    }
)
graph.add_edge("parse", "humor")
graph.add_edge("humor", "tts")
graph.add_edge("tts", END)

app = graph.compile()


async def main():
    initial_state = {
        "messages": [],
        "user_input": "",
        "search_results": {},
        "decision": "",
        "topic": "",
        "route_action": "",
        "parsed_output": "",  # Ensure initialized
        "response": "",        # Ensure initialized
        "full_text": ""        # Ensure initialized
    }
    await speak("Welcome boss")
    while True:
        try:
            res = await app.ainvoke(initial_state)
            if "exit" in res.get("route_action", "") or "goodbye" in str(res).lower():
                await speak("Goodbye boss")
                break
            initial_state = end_turn_node(res)
        except KeyboardInterrupt:
            await speak("Shutting down.")
            break
        except Exception as e:
            print(f"Loop error: {e}")
            # Ensure keys exist to avoid future KeyErrors
            initial_state["parsed_output"] = ""
            initial_state["response"] = ""
            initial_state["full_text"] = ""
            initial_state = end_turn_node(initial_state)
            await speak("Error occurred; continuing.")


import asyncio
if __name__ == "__main__":
    asyncio.run(main())