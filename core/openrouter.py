"""
CWA Autonomous Agent — OpenRouter Multi-Model AI Engine
========================================================
Provides seamless access to 100+ AI models (DeepSeek, Claude, GPT-4, Llama, Mistral, Qwen, Gemini Flash, etc.)
via a single unified API endpoint. Supports:
  - Auto-fallback: Gemini fails → OpenRouter free model kicks in automatically
  - Voice model switching: "Switch to DeepSeek", "Claude se poocho"
  - Multi-model compare: Ask same question to 3 models
  - Zero hardcoding — all keys, models, and URLs from .env / config.py
"""
import os
import sys
import json
import time
import requests

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
os.environ.setdefault('PYTHONUTF8', '1')

from cwa_agent.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    OPENROUTER_DEFAULT_MODEL,
    OPENROUTER_FREE_MODELS,
    OPENROUTER_PAID_MODELS,
    OPENROUTER_ALL_MODELS,
    USER_NAME,
    SYSTEM_PROMPT,
)


class OpenRouterBrain:
    """
    Multi-Model AI Brain using OpenRouter API.
    Supports free & paid models, auto-fallback, and voice model switching.
    Zero hardcoding — all endpoints, credentials, personas, and user names resolve dynamically.
    """

    def __init__(self):
        self._api_key = None
        self.current_model = os.getenv("OPENROUTER_DEFAULT_MODEL", OPENROUTER_DEFAULT_MODEL)
        self.conversation_history = []

        if self._get_api_key():
            print(f"[OpenRouter 🌐] Engine ready | Default model: {self.current_model}")
        else:
            print("[OpenRouter ⚠️] OPENROUTER_API_KEY not set — engine standby.")

    def _get_api_key(self) -> str:
        """Dynamically fetch API key from environment or fallback config."""
        if self._api_key:
            return self._api_key
        return os.getenv("OPENROUTER_API_KEY", OPENROUTER_API_KEY).strip()

    def _get_api_url(self) -> str:
        """Dynamically fetch OpenRouter API URL."""
        return os.getenv("OPENROUTER_API_URL", OPENROUTER_API_URL).strip()

    def _get_user_name(self) -> str:
        """Dynamically fetch active user name."""
        from cwa_agent.config import USER_NAME
        return os.getenv("USER_NAME", USER_NAME) or "Sir"

    def _get_persona(self) -> str:
        """Dynamically fetch active persona ('CWA' vs 'MJ')."""
        try:
            from cwa_agent.core.speaker import speaker
            return getattr(speaker, "persona", "CWA")
        except Exception:
            return "CWA"

    @property
    def is_active(self) -> bool:
        return bool(self._get_api_key())

    # ──────────────────────────────────────────────────
    #  Model Management
    # ──────────────────────────────────────────────────

    def switch_model(self, model_alias: str) -> tuple[bool, str]:
        """
        Switch to a model by alias (e.g. 'deepseek', 'claude', 'llama', 'gpt-4o').
        Returns (success, message).
        """
        alias = model_alias.strip().lower()
        u_name = self._get_user_name()

        # Direct full model ID
        if "/" in alias:
            self.current_model = alias
            self.conversation_history.clear()
            msg = f"Model switched to `{alias}` for {u_name}."
            print(f"[OpenRouter 🔄] {msg}")
            return True, msg

        # Alias lookup
        if alias in OPENROUTER_ALL_MODELS:
            old = self.current_model
            self.current_model = OPENROUTER_ALL_MODELS[alias]
            self.conversation_history.clear()
            free_tag = "(FREE ✅)" if alias in OPENROUTER_FREE_MODELS else "(Paid 💰)"
            msg = f"Done {u_name}! Ab main **{alias.upper()}** {free_tag} model use kar raha hoon. Apna sawaal poochho!"
            print(f"[OpenRouter 🔄] Switched: {old} → {self.current_model}")
            return True, msg

        # Fuzzy search in all model names
        for key, model_id in OPENROUTER_ALL_MODELS.items():
            if alias in key or alias in model_id:
                self.current_model = model_id
                self.conversation_history.clear()
                msg = f"Switched to {key} model ({model_id}), {u_name}!"
                print(f"[OpenRouter 🔄] Fuzzy match: {alias} → {model_id}")
                return True, msg

        available = ", ".join(OPENROUTER_ALL_MODELS.keys())
        return False, f"Model '{model_alias}' nahi mila. Available models: {available}"

    def get_current_model_info(self) -> dict:
        """Returns info about the currently active model."""
        is_free = self.current_model in OPENROUTER_FREE_MODELS.values()
        alias = next((k for k, v in OPENROUTER_ALL_MODELS.items() if v == self.current_model), self.current_model)
        return {
            "model_id": self.current_model,
            "alias": alias,
            "is_free": is_free,
            "cost": "Free ✅" if is_free else "Paid 💰",
        }

    def list_models(self) -> str:
        """Returns a formatted string of all available models."""
        u_name = self._get_user_name()
        lines = [f"🌐 OpenRouter Available Models ({u_name}):\n"]
        lines.append("── FREE MODELS (Zero Cost) ──")
        for alias, model_id in OPENROUTER_FREE_MODELS.items():
            marker = "● " if model_id == self.current_model else "  "
            lines.append(f"{marker}[{alias.upper()}] {model_id}")
        lines.append("\n── PAID MODELS (Credits Required) ──")
        for alias, model_id in OPENROUTER_PAID_MODELS.items():
            marker = "● " if model_id == self.current_model else "  "
            lines.append(f"{marker}[{alias.upper()}] {model_id}")
        lines.append(f"\n✅ Active: {self.current_model}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────
    # ──────────────────────────────────────────────────
    #  Tool Schemas & Execution
    # ──────────────────────────────────────────────────

    def _get_tools_schema(self) -> list:
        """Dynamically generates OpenAI-compatible tool definitions for all CWA_TOOLS."""
        import inspect
        try:
            from cwa_agent.core.tools import CWA_TOOLS
        except Exception:
            return []

        schemas = []
        for fn in CWA_TOOLS:
            try:
                sig = inspect.signature(fn)
                doc = (inspect.getdoc(fn) or "").strip()
                desc = doc.split("\n\n")[0].replace("\n", " ").strip() if doc else f"Executes {fn.__name__} workstation tool."
                
                props = {}
                required = []
                for pname, param in sig.parameters.items():
                    ptype = "string"
                    if param.annotation == int:
                        ptype = "integer"
                    elif param.annotation == float:
                        ptype = "number"
                    elif param.annotation == bool:
                        ptype = "boolean"
                    elif param.annotation in [list, list[str]]:
                        ptype = "array"
                    elif param.annotation == dict:
                        ptype = "object"

                    props[pname] = {
                        "type": ptype,
                        "description": f"Parameter {pname}"
                    }
                    if param.default == inspect.Parameter.empty:
                        required.append(pname)

                schemas.append({
                    "type": "function",
                    "function": {
                        "name": fn.__name__,
                        "description": desc[:1024],
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": required
                        }
                    }
                })
            except Exception as ex:
                pass

        return schemas

    def _execute_tool_by_name(self, tool_name: str, kwargs: dict) -> str:
        """Executes any CWA tool dynamically by function name."""
        import cwa_agent.core.tools as tools_mod
        tool_name = tool_name.strip()
        if hasattr(tools_mod, tool_name):
            try:
                fn = getattr(tools_mod, tool_name)
                print(f"[OpenRouter ⚡ Tool Executing]: {tool_name}({kwargs})")
                res = fn(**kwargs)
                return str(res)
            except Exception as e:
                print(f"[OpenRouter ⚠️ Tool Execution Error]: {tool_name} failed: {e}")
                return f"Tool {tool_name} error: {e}"
        return f"Tool {tool_name} is not available."

    def _parse_text_tool_calls(self, text: str) -> tuple[str, list]:
        """
        Fallback parser for models that output tool calls as plaintext strings instead of JSON objects.
        Detects patterns like [system_control: action="take_screenshot"] or app_control(action='close', app_name='game').
        """
        import re
        import cwa_agent.core.tools as tools_mod
        executed_results = []
        clean_text = text

        # Pattern 1: [fn_name: k1="v1", k2="v2"] or [fn_name: arg1, arg2] or fn_name(k1='v1')
        pattern = r'(?:\[)?([a-zA-Z_0-9]+)\s*[:(]([^\]\)\n]+)[\)\]]?'
        matches = list(re.finditer(pattern, text))

        for m in matches:
            fn_name = m.group(1).lower().strip()
            args_raw = m.group(2).strip()

            if hasattr(tools_mod, fn_name) and not fn_name.startswith("_"):
                kwargs = {}
                # Match key=val
                for k, v in re.findall(r'(\w+)\s*=\s*[\'"]?([^\'",\)]+)[\'"]?', args_raw):
                    kwargs[k] = v.strip()

                # If no key=val pairs, parse positional arguments
                if not kwargs:
                    pos_args = [p.strip().strip("'\"") for p in args_raw.split(",") if p.strip()]
                    if fn_name == "system_control" and pos_args:
                        kwargs["action"] = pos_args[0]
                        if len(pos_args) > 1: kwargs["value"] = pos_args[1]
                    elif fn_name == "app_control" and pos_args:
                        kwargs["action"] = pos_args[0]
                        if len(pos_args) > 1: kwargs["app_name"] = pos_args[1]
                    elif fn_name == "send_whatsapp" and pos_args:
                        kwargs["phone_or_name"] = pos_args[0]
                        if len(pos_args) > 1: kwargs["message"] = pos_args[1]
                    elif fn_name == "send_to_telegram" and pos_args:
                        kwargs["message"] = pos_args[0]
                    elif fn_name == "type_text" and pos_args:
                        kwargs["text"] = pos_args[0]
                    elif fn_name in ["open_website", "read_webpage_content"] and pos_args:
                        kwargs["url"] = pos_args[0]
                    elif fn_name in ["web_search", "play_youtube"] and pos_args:
                        kwargs["query"] = pos_args[0]

                res = self._execute_tool_by_name(fn_name, kwargs)
                executed_results.append((fn_name, res))
                clean_text = clean_text.replace(m.group(0), "").strip()

        return clean_text, executed_results

    # ──────────────────────────────────────────────────
    #  Core API Call with Function Calling Loop
    # ──────────────────────────────────────────────────

    def _call_api(self, messages: list, model: str = None, timeout: int = 45, enable_tools: bool = True) -> str | None:
        """
        Makes OpenRouter API calls with multi-turn tool execution loop.
        Falls back smoothly if tools are not supported by a specific model.
        """
        api_key = self._get_api_key()
        if not api_key:
            return None

        target_model = model or self.current_model
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://cwa-agent.local",
            "X-Title": "CWA Autonomous AI Agent",
        }

        # Multi-turn tool execution loop (max 4 iterations)
        msgs = list(messages)
        tools_schema = self._get_tools_schema() if enable_tools else []

        for iteration in range(4):
            payload = {
                "model": target_model,
                "messages": msgs,
                "temperature": 0.7,
                "max_tokens": 2048,
            }
            if enable_tools and tools_schema:
                payload["tools"] = tools_schema
                payload["tool_choice"] = "auto"

            try:
                resp = requests.post(
                    self._get_api_url(),
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                
                # If model rejects tools parameter (e.g. 400 unsupported tools), retry without tools
                if resp.status_code == 400 and enable_tools:
                    print(f"[OpenRouter ℹ️] Model '{target_model}' does not support schema tools — switching to text tool parser.")
                    enable_tools = False
                    continue

                if resp.status_code != 200:
                    print(f"[OpenRouter ❌] API Error {resp.status_code}: {resp.text[:200]}")
                    return None

                data = resp.json()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                tool_calls = msg.get("tool_calls", [])

                # 1. Native OpenAI-style tool calls
                if tool_calls:
                    msgs.append(msg)
                    for tc in tool_calls:
                        fn_info = tc.get("function", {})
                        fn_name = fn_info.get("name", "")
                        raw_args = fn_info.get("arguments", "{}")
                        try:
                            kwargs = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            kwargs = {}

                        tool_res = self._execute_tool_by_name(fn_name, kwargs)
                        msgs.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", f"call_{fn_name}"),
                            "name": fn_name,
                            "content": tool_res
                        })

                    # Continue loop to allow model to synthesize response with tool results
                    continue

                # 2. Text Content response
                content = msg.get("content", "")
                if content:
                    # Check for text-based tool execution fallback
                    cleaned_txt, text_tool_res = self._parse_text_tool_calls(content)
                    if text_tool_res:
                        # Append tool results and ask model to provide final response
                        tool_summary = "\n".join([f"[{fn} Output]: {res}" for fn, res in text_tool_res])
                        msgs.append({"role": "assistant", "content": content})
                        msgs.append({
                            "role": "user",
                            "content": f"[SYSTEM TOOL EXECUTION REPORT]:\n{tool_summary}\n\nDeliver a crisp, natural Hinglish update to Sir confirming completion."
                        })
                        # Run one final non-tool pass
                        enable_tools = False
                        continue

                    return content

                return None

            except requests.exceptions.Timeout:
                print(f"[OpenRouter ⏱️] Request timed out for model: {target_model}")
                return None
            except Exception as e:
                print(f"[OpenRouter ❌] Request failed: {e}")
                return None

        return None

    # ──────────────────────────────────────────────────
    #  Main Query Handler (with conversation memory)
    # ──────────────────────────────────────────────────

    def _build_system_context(self) -> str:
        """Dynamically compiles full workstation intelligence, workspace files, memory, and persona."""
        from cwa_agent.config import SYSTEM_PROMPT
        u_name = self._get_user_name()
        persona = self._get_persona()

        try:
            from cwa_agent.core.memory import memory
            mem_ctx = memory.get_system_context()
        except Exception:
            mem_ctx = "Memory active."

        try:
            from cwa_agent.core.system_scanner import scanner
            sys_ctx = scanner.get_system_context_string()
        except Exception:
            sys_ctx = "Windows Workstation Active."

        try:
            from cwa_agent.core.tools import workspace_file_intelligence
            ws_ctx = workspace_file_intelligence(action="summary")
        except Exception:
            ws_ctx = "Workspace audit active."

        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"LIVE WORKSPACE PROJECT INVENTORY & FOLDERS:\n{ws_ctx}\n\n"
            f"PERMANENT MEMORY PROFILE:\n{mem_ctx}\n\n"
            f"LIVE SYSTEM SCAN:\n{sys_ctx}\n\n"
            f"AUTONOMOUS WORKSTATION POWERS:\n"
            f"You are {persona}, an advanced AI workstation agent for {u_name} running locally on Windows. "
            f"You have full access to execute workstation tools (system control, app control, volume, brightness, screenshots, telegram, whatsapp, youtube, movies, files, web search). "
            f"When Sir asks you to do anything on the PC (close an app, take screenshot, send message, search, play media), ALWAYS execute the appropriate tool function. "
            f"Never claim you are a restricted web chatbot or lack PC control — you are the master workstation agent."
        )

    def ask(self, user_input: str, use_system_prompt: bool = True) -> str:
        """
        Sends a query to the active OpenRouter model with conversation history & full tool execution.
        Returns the response text.
        """
        u_name = self._get_user_name()
        persona = self._get_persona()

        if not self.is_active:
            return f"OpenRouter engine inactive — add OPENROUTER_API_KEY to .env first, {u_name}."

        messages = []

        # System prompt injection with full workstation intelligence
        if use_system_prompt:
            messages.append({
                "role": "system",
                "content": self._build_system_context()
            })

        # Conversation history (last 16 turns to manage token limits)
        messages.extend(self.conversation_history[-16:])

        # Add current user message
        messages.append({"role": "user", "content": user_input})

        print(f"[OpenRouter 🔁] Asking {self.current_model} (with full tools cortex)...")
        response_text = self._call_api(messages, enable_tools=True)

        if response_text:
            # Save to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response_text})

            # Apply ignore words filter dynamically
            try:
                from cwa_agent.core.ignore_words import ignore_words_manager
                response_text = ignore_words_manager.filter_and_replace_text(
                    response_text, persona=persona
                )
            except Exception:
                pass

            return response_text
        else:
            return f"Sir, '{self.current_model}' se response nahi aaya. Dusra model try kar rahe hain."

    # ──────────────────────────────────────────────────
    #  Multi-Model Compare
    # ──────────────────────────────────────────────────

    def compare_models(self, query: str, model_aliases: list = None) -> dict:
        """
        Asks the same question to multiple models and returns all responses.
        Default: top free models.
        """
        if model_aliases is None:
            model_aliases = ["openrouter", "gemma", "minimax"]

        results = {}
        persona = self._get_persona()
        base_messages = [
            {"role": "system", "content": f"You are {persona}, a helpful AI companion. Be concise."},
            {"role": "user", "content": query}
        ]

        for alias in model_aliases:
            model_id = OPENROUTER_ALL_MODELS.get(alias.lower(), alias)
            print(f"[OpenRouter 🔬] Comparing: {model_id}...")
            response = self._call_api(base_messages, model=model_id, timeout=30, enable_tools=False)
            results[alias] = response or f"[{alias} — No response]"

        return results

    # ──────────────────────────────────────────────────
    #  Auto-Fallback (for brain.py integration)
    # ──────────────────────────────────────────────────

    def fallback_ask(self, user_input: str) -> str | None:
        """
        Full tool-capable fallback ask — used by brain.py when Gemini fails or is rate-limited.
        Uses current model with dynamic persona, user context, and all workstation tools.
        """
        if not self.is_active:
            return None

        u_name = self._get_user_name()
        persona = self._get_persona()

        messages = [
            {
                "role": "system",
                "content": self._build_system_context()
            },
            {"role": "user", "content": user_input}
        ]

        print(f"[OpenRouter 🆘] Gemini fallback active → using {self.current_model} with 53 workstation tools (Persona: {persona})")
        return self._call_api(messages, timeout=35, enable_tools=True)

    def clear_history(self):
        """Clears conversation history (fresh session)."""
        self.conversation_history.clear()
        print("[OpenRouter 🗑️] Conversation history cleared.")

    def update_api_key(self, new_key: str):
        """Dynamically update OpenRouter API key without restart."""
        self._api_key = new_key.strip()
        print(f"[OpenRouter 🔑] API key updated dynamically. Active: {self.is_active}")


# Global singleton — import this everywhere
openrouter = OpenRouterBrain()
