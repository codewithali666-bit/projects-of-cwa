import os
import sys
import re
import json
import time
import datetime
from dataclasses import dataclass

# Fix Windows cp1252 encoding — allow emojis in print() on all Windows terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
os.environ.setdefault('PYTHONUTF8', '1')

from google import genai
from google.genai import types
from cwa_agent.config import GEMINI_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT, USER_NAME
from cwa_agent.core.tools import CWA_TOOLS

@dataclass
class AgentMoodResponse:
    """Represents a neural agent response enriched with dynamic emotion & sentiment metadata."""
    text: str
    emotion: str = "CALM"
    intensity: int = 50
    emoji: str = ""
    reason: str = "balanced"
    raw_text: str = ""

    def __str__(self):
        return self.text

def parse_emotion_response(raw_text: str) -> AgentMoodResponse:
    """
    Dynamically extracts emotion & emoji tags [MOOD: <EMOTION> | INTENSITY: <NUM> | EMOJI: <EMOJI> | REASON: <TEXT>]
    from LLM generated responses and returns an AgentMoodResponse with pure cleaned text.
    """
    if not raw_text:
        return AgentMoodResponse(text="", emotion="CALM", intensity=50, emoji="", reason="idle", raw_text="")
    
    emotion = "CALM"
    intensity = 75
    emoji_char = ""
    reason = "neural perception"

    tag_match = re.search(r"\[(?:MOOD|EMOTION):\s*([^\]]+)\]", raw_text, re.IGNORECASE)
    
    if tag_match:
        tag_content = tag_match.group(1)
        parts = [p.strip() for p in tag_content.split("|") if p.strip()]
        for i, part in enumerate(parts):
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip().upper()
                v = v.strip()
                if k in ["MOOD", "EMOTION"]:
                    emotion = v.upper()
                elif k == "INTENSITY" and v.isdigit():
                    intensity = int(v)
                elif k == "EMOJI":
                    emoji_char = v
                elif k == "REASON":
                    reason = v
            else:
                if i == 0:
                    emotion = part.upper()

    # Completely strip any bracket tags like [MOOD: ...], [WORKSPACE_FILE_INTELLIGENCE: ...], or [TAG: ...]
    clean_text = re.sub(r"\[[A-Z0-9_]+:[^\]]*\]", "", raw_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\[(?:MOOD|EMOTION|INTENSITY|EMOJI|REASON|WORKSPACE_FILE_INTELLIGENCE)[^\]]*\]", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\[[^\]]*\|[^\]]*\]", "", clean_text)
    clean_text = re.sub(r"^[a-zA-Z_0-9]+\([^)]*\)\s*", "", clean_text).strip()

    try:
        from cwa_agent.core.speaker import speaker
        from cwa_agent.core.ignore_words import ignore_words_manager
        clean_text = ignore_words_manager.filter_and_replace_text(clean_text, persona=getattr(speaker, 'persona', 'CWA'))
    except Exception:
        pass

    # If text is empty after removing tags (e.g. LLM returned tag only), provide a natural response
    if not clean_text:
        clean_text = "Haan Sir, bilkul!"

    return AgentMoodResponse(
        text=clean_text,
        emotion=emotion,
        intensity=min(100, max(0, intensity)),
        emoji=emoji_char,
        reason=reason,
        raw_text=raw_text
    )


class CWABrain:
    def __init__(self, api_key: str = None, model_name: str = GEMINI_MODEL):
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name
        self.client = None
        self.chat = None
        self.on_clear_callbacks = []
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            print("[Brain Notice] GEMINI_API_KEY is not set yet.")
            return False

        try:
            from cwa_agent.core.memory import memory
            from cwa_agent.core.system_scanner import scanner
            from cwa_agent.core.tools import workspace_file_intelligence
            mem_ctx = memory.get_system_context()
            sys_ctx = scanner.get_system_context_string()
            try:
                ws_ctx = workspace_file_intelligence(action="summary")
            except Exception:
                ws_ctx = "Workspace audit active."

            dynamic_system_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"LIVE WORKSPACE PROJECT INVENTORY & FOLDERS:\n{ws_ctx}\n\n"
                f"PERMANENT MEMORY PROFILE:\n{mem_ctx}\n\n"
                f"LIVE SYSTEM SCAN (Performed at boot):\n{sys_ctx}"
            )

            self.client = genai.Client(api_key=self.api_key)
            self.chat = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=dynamic_system_prompt,
                    temperature=0.7,   # Balanced for reliable tool execution & natural conversation
                    tools=CWA_TOOLS
                )
            )
            print(f"[Brain 🧠] CWA Neural Cortex active with '{self.model_name}', workspace file inventory, memory+system scan context, and {len(CWA_TOOLS)} tools.")
            return True
        except Exception as e:
            print(f"[Brain Error] Failed to initialize Gemini Client: {e}")
            self.on_clear_callbacks = []
            return False


    def set_api_key(self, key: str) -> bool:
        """Sets or updates the Gemini API Key dynamically."""
        self.api_key = key.strip()
        return self._init_client()

    def register_clear_callback(self, cb):
        """Registers a callback to be called when chat memory is wiped."""
        self.on_clear_callbacks.append(cb)

    def clear_chat(self) -> AgentMoodResponse:
        """Resets the Gemini chat session (clears all memory) and returns a dynamic confirmation."""
        try:
            from cwa_agent.core.memory import memory
            mem_ctx = memory.get_system_context()
            dynamic_system_prompt = f"{SYSTEM_PROMPT}\n\nPERMANENT MEMORY PROFILE:\n{mem_ctx}"

            self.chat = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=dynamic_system_prompt,
                    temperature=0.9,   # Higher = more natural, human-like, creative
                    tools=CWA_TOOLS
                )
            )
            print("[Brain 🧹] Chat history cleared. Fresh session started.")

            for cb in self.on_clear_callbacks:
                try:
                    cb()
                except Exception as e:
                    print(f"[Brain Callback Error]: {e}")

            return self.process_query(
                f"The user just cleared the active chat. Acknowledge this in a fresh, witty 1-sentence JARVIS style to {USER_NAME}. Do NOT use any tool."
            )
        except Exception as e:
            return AgentMoodResponse(text=f"Memory reset attempted, Sir. ({e})", emotion="CALM", intensity=40, reason="reset error")

    def generate_greeting(self) -> AgentMoodResponse:
        """Generates a 100% dynamic, context-aware startup greeting with emotion & memory context using Gemini."""
        current_hour = datetime.datetime.now().hour
        time_context = "morning" if 5 <= current_hour < 12 else "afternoon" if 12 <= current_hour < 17 else "evening" if 17 <= current_hour < 22 else "night"
        
        from cwa_agent.core.memory import memory
        mem_ctx = memory.get_system_context()
        prompt = (
            f"You have just booted up. Give a short, energetic, 1-sentence JARVIS greeting to {USER_NAME} acknowledging that it is {time_context}. "
            f"If relevant from your memory profile: [{mem_ctx}], naturally welcome Sir back to his active work or day."
        )
        return self.process_query(prompt)

    def generate_idle_checkin(self) -> AgentMoodResponse:
        """Generates a 100% dynamic, witty companion check-in when user has been quiet for a few minutes."""
        current_hour = datetime.datetime.now().hour
        time_context = "morning" if 5 <= current_hour < 12 else "afternoon" if 12 <= current_hour < 17 else "evening" if 17 <= current_hour < 22 else "night"
        from cwa_agent.core.memory import memory
        mem_ctx = memory.get_system_context()
        
        prompt = (
            f"The user has been working quietly for a few minutes. Give a very short, fresh, 1-sentence friendly check-in to {USER_NAME} "
            f"asking how it is going, offering quick assistance, or sharing a brief witty observation in natural Hinglish or English. "
            f"Relevant context: [{mem_ctx}]. Keep it natural, warm, and concise."
        )
        return self.process_query(prompt)

    def generate_shutdown(self) -> AgentMoodResponse:
        """Generates a dynamic farewell message and updates last session memory using Gemini."""
        from cwa_agent.core.memory import memory
        memory.update_last_session(summary="Workstation shutdown/farewell completed")
        prompt = f"The user is shutting down or saying goodbye. Give a short, witty or warm 1-sentence JARVIS response to {USER_NAME}."
        return self.process_query(prompt)

    def generate_game_commentary(self, event_type: str, pos_desc: str = "", score_info: str = "") -> str:
        """Generates dynamic AI game commentary and banter on-the-fly using Gemini Neural Engine."""
        from cwa_agent.config import USER_NAME
        u_name = USER_NAME or "Sir"
        prompt = (
            f"[LIVE GAMEPLAY EVENT]: Tic-Tac-Toe match with {u_name}. "
            f"Event: {event_type} | Move/Position: '{pos_desc}' | Scoreboard: {score_info}. "
            f"Generate a dynamic, witty, 1-sentence game commentary in natural Hinglish directly addressing {u_name}. Do not output quotes or brackets."
        )
        try:
            if self.client:
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.85, max_output_tokens=60)
                )
                if resp and resp.text:
                    txt = resp.text.strip().replace('"', '').replace('\n', ' ')
                    if txt:
                        return txt
        except Exception:
            pass

        # Dynamic fallback
        if event_type == "user_win":
            return f"Shandar {u_name}! Aap yeh match jeet gaye! Fantastic strategy!"
        elif event_type == "ai_win":
            return f"Maine 3 in a row complete kar liya {u_name}! Yeh round mera hua."
        elif event_type == "draw":
            return f"Match tie ho gaya {u_name}! Dono taraf se solid defense tha."
        elif event_type == "ai_move":
            return f"Maine {pos_desc} par 'O' chala hai. Ab aapki bari hai (X), {u_name}!"
        elif event_type == "invalid_move":
            return f"{u_name}, yeh box already occupied hai, doosra choose kijiye."
        elif event_type == "game_over":
            return f"{u_name}, match over ho chuka hai, 'NEW' dabakar naya game start kijiye."
        return f"{u_name}, aapki move hai (X)."

    def process_query(self, user_input: str) -> AgentMoodResponse:
        """
        Sends user input to Gemini Agent, processes tools dynamically, and returns an AgentMoodResponse with emotion.
        """
        if not self.client or not self.chat:
            if not self._init_client():
                return AgentMoodResponse(
                    text="Sir, please configure your Gemini API Key in the settings or .env file so I can access full neural cognition.",
                    emotion="CALM",
                    intensity=50,
                    reason="api key missing"
                )

        clean_input = user_input.strip()
        if not clean_input:
            return AgentMoodResponse(
                text="Standing by for your instructions, Sir.",
                emotion="CALM",
                intensity=40,
                reason="standing by"
            )

        try:
            print(f"\n[Brain 💭 Thinking...]: Processing request '{clean_input}'")
            response = self.chat.send_message(clean_input)
            final_text = response.text.strip() if response.text else ""

            # Check if Gemini outputted a text-based tool call instead of natural speech
            import re
            tool_match = re.search(r'\[?([a-zA-Z_0-9]+)\s*[:(]([^\]\)]+)\]?', final_text)
            if tool_match:
                candidate_fn = tool_match.group(1).lower().strip()
                raw_args = tool_match.group(2).strip()
                from cwa_agent.core import tools as tools_module
                if hasattr(tools_module, candidate_fn) and candidate_fn in [
                    "send_whatsapp", "app_control", "workspace_file_intelligence",
                    "media_search_and_download", "file_manager", "system_control",
                    "manage_ignore_words", "manage_forbidden_words", "navigate_route",
                    "search_nearby_places", "remove_image_background", "openrouter_switch_model",
                    "openrouter_ask", "openrouter_compare", "openrouter_status"
                ]:
                    tool_fn = getattr(tools_module, candidate_fn)
                    kwargs = {}
                    for k, v in re.findall(r'(\w+)\s*=\s*[\'"]?([^\'",\s]+)[\'"]?', raw_args):
                        kwargs[k] = v
                    if not kwargs:
                        pos_args = [p.strip().strip("'\"") for p in raw_args.split(",") if p.strip()]
                        if candidate_fn == "system_control" and pos_args:
                            kwargs["action"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["value"] = pos_args[1]
                        elif candidate_fn == "app_control" and pos_args:
                            kwargs["action"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["app_name"] = pos_args[1]
                        elif candidate_fn == "send_whatsapp" and pos_args:
                            kwargs["phone_or_name"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["message"] = pos_args[1]
                        elif candidate_fn == "navigate_route" and pos_args:
                            kwargs["origin"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["destination"] = pos_args[1]
                            if len(pos_args) > 2:
                                kwargs["travel_mode"] = pos_args[2]
                        elif candidate_fn == "search_nearby_places" and pos_args:
                            kwargs["query"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["location"] = pos_args[1]
                        elif candidate_fn == "remove_image_background" and pos_args:
                            kwargs["image_path_or_url"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["bg_color"] = pos_args[1]
                        elif candidate_fn in ["openrouter_switch_model", "openrouter_ask"] and pos_args:
                            kwargs["model_name" if candidate_fn == "openrouter_switch_model" else "question"] = pos_args[0]
                        elif candidate_fn in ["manage_ignore_words", "manage_forbidden_words"] and pos_args:
                            kwargs["action"] = pos_args[0]
                            if len(pos_args) > 1:
                                kwargs["word_or_phrase"] = pos_args[1]
                            if len(pos_args) > 2:
                                kwargs["replace_with"] = pos_args[2]
                            if len(pos_args) > 3:
                                kwargs["persona"] = pos_args[3]

                    try:
                        print(f"[Brain ⚡ Auto-Executing Tool]: {candidate_fn}({kwargs})")
                        tool_result = tool_fn(**kwargs)
                        followup = self.chat.send_message(
                            f"[TOOL OUTPUT FOR '{clean_input}']:\n{tool_result}\n\n"
                            f"Explain the above findings to Sir in warm, natural Hinglish/English. Do not output code or brackets."
                        )
                        if followup.text:
                            final_text = followup.text.strip()
                    except Exception as ex:
                        print(f"[Brain Auto-Tool Execution Error]: {ex}")

            if not final_text:
                final_text = "Haan Sir, action complete ho gaya!"

            return parse_emotion_response(final_text)

        except Exception as e:
            error_msg = str(e)
            print(f"[Brain Error]: {error_msg}")

            # ── OpenRouter Auto-Fallback: Try OpenRouter when Gemini fails ──
            try:
                from cwa_agent.core.openrouter import openrouter
                if openrouter.is_active:
                    print(f"[Brain 🔄] Gemini failed — switching to OpenRouter fallback ({openrouter.current_model})...")
                    fallback_text = openrouter.fallback_ask(clean_input)
                    if fallback_text:
                        return parse_emotion_response(fallback_text)
            except Exception as fb_err:
                print(f"[Brain Fallback Error]: {fb_err}")

            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                if self.model_name != "gemini-flash-latest":
                    try:
                        self.model_name = "gemini-flash-latest"
                        self._init_client()
                        fb_response = self.chat.send_message(clean_input)
                        if fb_response.text:
                            return parse_emotion_response(fb_response.text.strip())
                    except Exception:
                        pass
                return AgentMoodResponse(
                    text=f"Sir, Google API traffic rate limit hai. OpenRouter mein request try kar raha hoon... agar ab bhi nahi aaya to thoda wait karein.",
                    emotion="CALM",
                    intensity=50,
                    reason="rate limit — openrouter fallback attempted"
                )

            elif "API_KEY" in error_msg.upper() or "UNAUTHENTICATED" in error_msg.upper():
                return AgentMoodResponse(
                    text="Sir, the Gemini API key appears to be invalid or expired. Please check your credentials.",
                    emotion="ANGRY",
                    intensity=60,
                    reason="authentication issue"
                )

            return AgentMoodResponse(
                text=f"Sir, I am online and executing: {clean_input}",
                emotion="CALM",
                intensity=50,
                reason="execution"
            )

# Global instance
brain = CWABrain()
