import re
from app.schemas import Agent
from pydantic import ValidationError


# Function to strip markdown from the content
def preprocess_text(text: str) -> str:
    if not text:
        return ""
    # Remove triple backticks (```), but keep inner content
    text = re.sub(r'```+', '', text)

    # Remove hyphens and dashes
    text = re.sub(r'-', '', text)

    # Remove headers (e.g., ## Header)
    text = re.sub(r'(^|\n)\s*#{1,6}\s*', r'\1', text)

    # Remove bold and italic markers
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)  # Bold
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)     # Italic
    text = re.sub(r'~~(.*?)~~', r'\1', text)         # Strikethrough

    # Remove inline code markers
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove fenced code block markers but keep the code content
    text = re.sub(r'```[\w]*\n([\s\S]*?)```', r'\1', text)

    # Replace [text](link) with just text
    text = re.sub(r'\[(.*?)\]\([^)]*\)', r'\1', text)

    # Replace ![alt](image) with just alt text
    text = re.sub(r'!\[(.*?)\]\([^)]*\)', r'\1', text)

    return text


def safe_str(value):
    from bson import ObjectId
    return str(value) if isinstance(value, ObjectId) else value

def parse_agent_config(raw_json: dict) -> Agent:
    """
    Converts UI JSON (with 'nodes', 'edges', etc.) to AgentConfig model.
    Assumes node data is inside node["data"].
    """
    try:
        global_settings = raw_json.get("global_settings")
        user_id = safe_str(raw_json.get("user_id"))
        agent_display_name = raw_json.get("flow_id")
        entry_node = raw_json.get("entry_node")
        flow_type=raw_json.get("flow_type")
        custom_functions= raw_json.get("custom_functions")

        ui_nodes = raw_json.get("nodes", [])
        parsed_nodes = []

        for node in ui_nodes:
            node_data = node.get("data", {})
            if not node_data:
                continue
            parsed_nodes.append(NodeConfig(**node_data))

        agent_config = AgentConfig(
            global_settings=GlobalSettings(**global_settings) if global_settings else None,
            agent_display_name = agent_display_name,
            entry_node=entry_node,
            nodes=parsed_nodes,
            flow_type=flow_type,
            custom_functions=custom_functions,
            user_id=user_id
        )

        return agent_config

    except ValidationError as e:
        print("Validation error while parsing agent config:", e)
        raise
