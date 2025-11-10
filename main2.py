import asyncio
import os
os.environ['JACK_NO_AUDIO_RESERVATION'] = '1'
os.environ['PYALSA_IGNORE_DLOPEN_ERRORS'] = '1'
os.environ['ALSA_PCM_CARD'] = '0'
import datetime
import json
import subprocess
import tempfile
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import DuckDuckGoSearchResults
import speech_recognition as sr
import edge_tts 
from dotenv import load_dotenv

load_dotenv()

DOC_FOLDER = os.path.expanduser("~/aether_docs")
os.makedirs(DOC_FOLDER, exist_ok=True)


os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning'


os.environ["GOOGLE_API_KEY"] = os.getenv("GEMI_API")

# State Schema
class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_input: str
    search_results: dict
    decision: str
    topic: str
    action: str  


llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
search_results_tool = DuckDuckGoSearchResults(num_results=5)
recognizer = sr.Recognizer()
mic = sr.Microphone()


async def listen_node(state: State) -> State:
    print("Listening... (Say 'exit' to quit)")
    await speak("Listening")
    state["user_input"] = ""
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
        text = recognizer.recognize_google(audio).lower()
        print(f"You said: {text}")
        state["user_input"] = text
        if "exit" in text:
            await speak("Goodbye")
            return {**state, "messages": state["messages"] + [AIMessage(content="Goodbye!")]}
    except sr.UnknownValueError:
        print("Sorry, didn't catch that. Typing fallback:")
    except (sr.RequestError, sr.WaitTimeoutError):
        print("Mic/STT issue; using text input.")
    except Exception as e:
        print(f"Listen error: {e}; using text input.")

    if not state["user_input"]:
        state["user_input"] = input("> ").lower()
    return state


async def speak(text: str):
    def _edge_tts_and_play():
        try:
            communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural", rate="-8%", pitch="-6Hz")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_file = tmp.name
            with open(tmp_file, "wb") as wf:
                for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        wf.write(chunk["data"])
            if subprocess.call(["which", "aplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                subprocess.run(["aplay", tmp_file], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif subprocess.call(["which", "paplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                subprocess.run(["paplay", tmp_file], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(['espeak', '-s', '200', '-v', 'en-us', text], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.unlink(tmp_file)  # Cleanup
        except Exception as e:
            print(f"TTS playback error: {e}")
            subprocess.run(['espeak', '-s', '150', '-v', 'en-us', text], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.to_thread(_edge_tts_and_play)


async def speak_and_print(text: str, state: State = None):
    print(text)
    if state and state["messages"]:
        last_msg = state["messages"][-1]
        if hasattr(last_msg, 'content'):
            last_msg.content += text + "\n"
    await speak(text)


def process_query_node(state: State) -> State:
    prompt = f"""
    Analyze: '{state['user_input']}'
    Extract topic (concise phrase).
    Needs search? (yes/no for questions/info).
    JSON only: {{"topic": "str", "needs_search": "yes/no"}}
    """
    response = llm.invoke(prompt)
    try:
        content = response.content.strip()
        start = content.find('{')
        end = content.rfind('}') + 1
        parsed = json.loads(content[start:end])
        state["topic"] = parsed.get("topic", state["user_input"])
        state["action"] = "search" if parsed.get("needs_search", "yes") == "yes" else "direct"
    except Exception:
        state["topic"] = state["user_input"]
        state["action"] = "search"  
    state["messages"].append(HumanMessage(content=state["user_input"]))
    if state["action"] == "direct":
        state["messages"].append(AIMessage(content="Direct command noted."))
    return state

async def search_node(state: State) -> State:
    query = state["topic"]
    if "?" in state["user_input"] or "what" in state["user_input"]:
        query += " overview"
    formatted = []
    try:
        raw_results_str = search_results_tool.run(query) 
        print(raw_results_str)
        if not raw_results_str or not raw_results_str.strip():
            raise ValueError("Empty search response")
        
        raw_results = []
        delimiter = ', snippet: '
        parts = raw_results_str.split(delimiter) if delimiter in raw_results_str else [raw_results_str]
        for idx, part in enumerate(parts):
            if not part.strip():
                continue
            try:
                if idx == 0 and part.startswith('snippet: '):
                    snippet_str = part[9:]
                else:
                    snippet_str = part
                snippet, rest = snippet_str.split(', title: ', 1)
                title, link_str = rest.split(', link: ', 1)
                link = link_str.strip().rstrip(',')
                raw_results.append({
                    'snippet': snippet.strip(),
                    'title': title.strip(),
                    'href': link
                })
            except ValueError:
                print(f"Skipping malformed search part: {part[:50]}...")
                continue
        
        if not raw_results:
            raise ValueError("No valid results parsed")
        
        for i, res in enumerate(raw_results, 1):
            snippet = res.get('snippet', 'No snippet')
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            source = res.get('href', res.get('link', 'Unknown'))
            entry = f"{i}. {snippet}\n   Source: {source}"
            formatted.append(entry)
            await speak_and_print(entry)
    except Exception as e:
        error_msg = f"Search error: {e}"
        formatted = [error_msg]
        await speak_and_print(error_msg)
    
    state["search_results"] = {state["topic"]: formatted}
    state["messages"].append(AIMessage(content="\n".join(formatted)))
    return state

# Node: Decide on doc creation
async def decide_doc_node(state: State) -> State:
    question = f"Want to create a document on '{state['topic']}? Say yes/no."
    await speak_and_print(question)
    sub_state = await listen_node(State(messages=state["messages"]))
    state["decision"] = sub_state["user_input"]
    return state

# Node: Create document
async def create_doc_node(state: State) -> State:
    if "yes" not in state["decision"].lower():
        return state
    topic = state["topic"]
    results = state["search_results"].get(topic, [])
    if len(results) == 1 and "error" in results[0].lower():
        await speak_and_print("Search failed; skipping doc creation.")
        return state
    md_content = f"# {topic.title()}\n\nGenerated: {datetime.datetime.now()}\n\n"
    for res in results:
        if "Source:" in res and "error" not in res.lower():
            section, src = res.split("\n   Source: ", 1)
            title = section.split('.', 1)[1].strip() if '.' in section else 'Info'
            md_content += f"## {title}\n{section}\n\nSource: {src}\n\n"
        else:
            md_content += f"## Note\n{res}\n\n"
    md_content += "## Sources\nWeb search via DuckDuckGo."
    filename = f"{topic.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md"
    filepath = os.path.join(DOC_FOLDER, filename)
    with open(filepath, "w") as f:
        f.write(md_content)
    confirmation = f"Document saved: {filepath}"
    await speak_and_print(confirmation)
    state["messages"].append(AIMessage(content=confirmation))
    return state

# Node: General response
async def respond_node(state: State) -> State:
    if state["search_results"]:
        summary = f"Done with {state['topic']}. Ask more?"
        await speak_and_print(summary)
    elif state.get("decision") and "no" in state["decision"].lower():
        await speak_and_print("No doc. Next?")
    else:
        await speak_and_print("How can I help?")
    return state

# Node: End turn
def end_turn_node(state: State) -> State:
    state["search_results"] = {}
    state["decision"] = ""
    state["user_input"] = ""
    state["topic"] = ""
    state["action"] = ""
    return state

# Build Graph - Fixed flow: conditional after process
workflow = StateGraph(State)
workflow.add_node("listen", listen_node)
workflow.add_node("process", process_query_node)
workflow.add_node("search", search_node)
workflow.add_node("decide", decide_doc_node)
workflow.add_node("create_doc", create_doc_node)
workflow.add_node("respond", respond_node)
workflow.add_node("end_turn", end_turn_node)

workflow.set_entry_point("listen")
workflow.add_edge("listen", "process")

# Conditional after process: search or direct to respond
workflow.add_conditional_edges(
    "process",
    lambda s: s.get("action", "direct"),
    {"search": "search", "direct": "respond"}
)

# After search: check for direct create or decide
workflow.add_conditional_edges(
    "search",
    lambda s: "create_doc" if "create doc" in s["user_input"].lower() else "decide",
    {"create_doc": "create_doc", "decide": "decide"}
)

workflow.add_conditional_edges(
    "decide",
    lambda s: "create_doc" if "yes" in s["decision"].lower() else "respond",
    {"create_doc": "create_doc", "respond": "respond"}
)
workflow.add_edge("create_doc", "respond")
workflow.add_edge("respond", "end_turn")
workflow.add_edge("end_turn", "listen")

app = workflow.compile()

async def main():
    initial_state = {"messages": [], "user_input": "", "search_results": {}, "decision": "", "topic": "", "action": ""}
    while True:
        try:
            result = await app.ainvoke(initial_state)
            if "goodbye" in str(result).lower() or "exit" in result.get("user_input", ""):
                await speak("Goodbye")
                break
            initial_state = end_turn_node(result)
        except KeyboardInterrupt:
            await speak("Shutting down.")
            break
        except Exception as e:
            print(f"Loop error: {e}")
            initial_state = end_turn_node(initial_state)
            await speak("Error occurred; continuing.")

if __name__ == "__main__":
    asyncio.run(main())