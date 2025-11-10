from typing import TypedDict, List, Dict, Any

class State(TypedDict):
    messages: List[Any]
    user_input: str
    search_results: Dict[str, Any]
    decision: str
    topic: str
    route_action: str
    parsed_output: str
    response: str
    full_text: str