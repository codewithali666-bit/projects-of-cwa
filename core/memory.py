import os
import sys
import json
import time
import datetime
from pathlib import Path
from cwa_agent.config import DATA_DIR, USER_NAME

# Fix Windows cp1252 encoding — allow emojis in print() on all Windows terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
os.environ.setdefault('PYTHONUTF8', '1')

MEMORY_FILE = DATA_DIR / "memory.json"

class LongTermMemory:
    """
    Persistent Long-Term Episodic Memory Brain for CWA-JARVIS.
    Stores and recalls facts, user preferences, active projects, and past session summaries
    across app restarts.
    """
    def __init__(self, memory_path: Path = MEMORY_FILE):
        self.memory_path = memory_path
        self.data = {
            "user_name": USER_NAME,
            "preferences": {
                "preferred_language": "Hinglish",
                "interface_theme": "Stark Sci-Fi HUD",
                "default_persona": "CWA"
            },
            "facts": [],
            "active_projects": {},
            "reminders": [],
            "forbidden_words": [],
            "last_session": {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "summary": "System initialized"
            }
        }
        self._load_memory()

    def _load_memory(self):
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"[Memory Warning] Could not load memory.json: {e}")
        else:
            self._save_memory()

    def _save_memory(self):
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Memory Error] Could not save memory.json: {e}")

    def remember_fact(self, fact: str, category: str = "general") -> str:
        """Saves a permanent fact or detail about Sir into persistent memory."""
        if not fact or not fact.strip():
            return "No fact specified to remember."

        clean_fact = fact.strip()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Avoid duplicate facts
        for existing in self.data["facts"]:
            if existing.get("fact", "").lower() == clean_fact.lower():
                return f"I already remember that, Sir: '{clean_fact}'"

        self.data["facts"].append({
            "fact": clean_fact,
            "category": category.strip().lower(),
            "timestamp": timestamp
        })
        self._save_memory()
        print(f"[Memory 🧠 Saved]: '{clean_fact}' (Category: {category})")
        return f"Understood, Sir. I have committed this to my permanent memory: '{clean_fact}'"

    def recall_memory(self, query: str = "") -> str:
        """Retrieves stored facts, preferences, or active projects from persistent memory."""
        facts = self.data.get("facts", [])
        projects = self.data.get("active_projects", {})
        prefs = self.data.get("preferences", {})

        if not facts and not projects:
            return "No personal facts or active projects recorded in memory yet, Sir."

        clean_q = query.lower().strip() if query else ""
        
        if clean_q:
            matched = [f["fact"] for f in facts if any(word in f["fact"].lower() for word in clean_q.split())]
            if matched:
                return "Here is what I remember regarding your query:\n" + "\n".join(f"- {m}" for m in matched)

        # General memory overview
        result = [f"### Permanent Memory Profile for {self.data.get('user_name', 'Sir')}:"]
        if facts:
            result.append("Key Facts & Notes:")
            for f in facts[-8:]:  # Last 8 facts
                result.append(f"- [{f.get('category', 'general')}] {f.get('fact')}")
        if projects:
            result.append("\nActive Projects:")
            for name, desc in projects.items():
                result.append(f"- {name}: {desc}")

        return "\n".join(result)

    def set_project(self, project_name: str, description: str) -> str:
        """Tracks an active ongoing project."""
        self.data["active_projects"][project_name.strip()] = description.strip()
        self._save_memory()
        return f"Project '{project_name}' is now registered in active neural memory."

    def update_last_session(self, summary: str = ""):
        """Updates last session timestamp and conversation summary on shutdown."""
        self.data["last_session"] = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary.strip() if summary else "Session concluded smoothly"
        }
        self._save_memory()

    def get_system_context(self) -> str:
        """Generates dynamic memory context to inject into Gemini Neural Cortex on boot."""
        facts = self.data.get("facts", [])
        projects = self.data.get("active_projects", {})
        last_sess = self.data.get("last_session", {})
        
        lines = []
        if facts:
            lines.append("KNOWN FACTS ABOUT SIR:")
            for f in facts[-6:]:
                lines.append(f"- {f.get('fact')}")
        if projects:
            lines.append("ACTIVE PROJECTS:")
            for p, d in projects.items():
                lines.append(f"- {p}: {d}")
        if last_sess.get("timestamp"):
            lines.append(f"LAST SESSION: {last_sess.get('timestamp')} (Summary: {last_sess.get('summary')})")

        from cwa_agent.core.ignore_words import ignore_words_manager
        ignore_ctx = ignore_words_manager.get_system_prompt_context()
        if ignore_ctx:
            lines.append(f"\n{ignore_ctx}")

        return "\n".join(lines) if lines else "No prior history recorded."

    def add_forbidden_word(self, word: str, persona: str = "auto") -> str:
        """Permanently adds a word or phrase to the forbidden list so CWA/MJ never says or writes it."""
        from cwa_agent.core.ignore_words import ignore_words_manager
        return ignore_words_manager.add_forbidden_word(word, persona=persona)

    def remove_forbidden_word(self, word: str, persona: str = "auto") -> str:
        """Removes a word or phrase from the persistent forbidden list."""
        from cwa_agent.core.ignore_words import ignore_words_manager
        return ignore_words_manager.remove_rule(word, persona=persona)

    def get_forbidden_words(self, persona: str = None) -> list:
        """Returns all currently forbidden words/phrases."""
        from cwa_agent.core.ignore_words import ignore_words_manager
        return ignore_words_manager.get_forbidden_words(persona=persona)

    def filter_forbidden_words(self, text: str, persona: str = None) -> str:
        """Dynamically censors/removes any forbidden words and applies word replacements."""
        from cwa_agent.core.ignore_words import ignore_words_manager
        return ignore_words_manager.filter_and_replace_text(text, persona=persona)

# Global LongTermMemory Singleton
memory = LongTermMemory()
