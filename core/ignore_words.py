"""
CWA Autonomous Agent — Persona-Specific Ignore & Forbidden Words Intelligence Engine
Manages forbidden words, phrases, and replacement rules separated for Male (CWA) and Female (MJ) personas.
Persisted in dynamic JSON files inside cwa_agent/data/ignore_words/.
"""
import os
import re
import json
import time
from pathlib import Path
from cwa_agent.config import DATA_DIR

IGNORE_WORDS_DIR = DATA_DIR / "ignore_words"
IGNORE_WORDS_DIR.mkdir(parents=True, exist_ok=True)

MALE_FILE = IGNORE_WORDS_DIR / "male_ignore_words.json"
FEMALE_FILE = IGNORE_WORDS_DIR / "female_ignore_words.json"
GLOBAL_FILE = IGNORE_WORDS_DIR / "global_ignore_words.json"


class IgnoreWordsManager:
    """
    Persona-Aware Ignore & Forbidden Words Engine.
    Maintains separate rules for Male (CWA), Female (MJ), and Global personas.
    """
    def __init__(self):
        self.male_rules = self._load_file(MALE_FILE, "male")
        self.female_rules = self._load_file(FEMALE_FILE, "female")
        self.global_rules = self._load_file(GLOBAL_FILE, "global")

    def _load_file(self, file_path: Path, persona_name: str) -> dict:
        """Loads or initializes a persona rules JSON file dynamically."""
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data.setdefault("forbidden_words", [])
                        data.setdefault("word_replacements", {})
                        data.setdefault("speech_guidelines", [])
                        return data
            except Exception as e:
                print(f"[IgnoreWords Notice] Failed reading {file_path.name}: {e}")

        default_data = {
            "persona": persona_name,
            "forbidden_words": [],
            "word_replacements": {},
            "speech_guidelines": [],
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save_file(file_path, default_data)
        return default_data

    def _save_file(self, file_path: Path, data: dict):
        """Saves persona rules to disk with atomic write."""
        try:
            data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            temp_path = file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(file_path)
        except Exception as e:
            print(f"[IgnoreWords Error] Failed saving {file_path.name}: {e}")

    def _resolve_target(self, persona: str = "auto") -> list:
        """Resolves target rule dicts and files based on persona selection."""
        p = str(persona).lower().strip()
        if p in ["male", "cwa", "jarvis", "boy", "ladka"]:
            return [(self.male_rules, MALE_FILE, "Male (CWA)")]
        elif p in ["female", "mj", "girl", "ladki"]:
            return [(self.female_rules, FEMALE_FILE, "Female (MJ)")]
        elif p in ["both", "global", "all", "sab", "dono"]:
            return [(self.global_rules, GLOBAL_FILE, "Global (Both Personas)")]
        else:
            # Auto: detect currently active persona from speaker
            try:
                from cwa_agent.core.speaker import speaker
                active_p = getattr(speaker, 'persona', 'CWA')
                if active_p == "MJ":
                    return [(self.female_rules, FEMALE_FILE, "Female (MJ)")]
                else:
                    return [(self.male_rules, MALE_FILE, "Male (CWA)")]
            except Exception:
                return [(self.global_rules, GLOBAL_FILE, "Global")]

    def add_forbidden_word(self, word: str, persona: str = "auto") -> str:
        """
        Permanently forbids a word or phrase for the specified persona so it is NEVER spoken or printed.
        """
        if not word or not str(word).strip():
            return "No word or phrase specified to forbid, Sir."

        clean_w = str(word).strip()
        targets = self._resolve_target(persona)
        added_to = []

        for rules, file_path, label in targets:
            existing = rules.get("forbidden_words", [])
            if any(e.lower() == clean_w.lower() for e in existing):
                continue
            existing.append(clean_w)
            rules["forbidden_words"] = existing
            self._save_file(file_path, rules)
            added_to.append(label)

        if added_to:
            print(f"[IgnoreWords [X] Added]: '{clean_w}' for {', '.join(added_to)}")
            return f"Done Sir. The word/phrase '{clean_w}' is now permanently forbidden for {', '.join(added_to)}. I will never say or write it."
        else:
            return f"Sir, '{clean_w}' was already in the forbidden list for {targets[0][2]}."

    def add_word_replacement(self, word_or_phrase: str, replace_with: str, persona: str = "auto") -> str:
        """
        Sets a word replacement rule so whenever the assistant would say word_or_phrase,
        it automatically replaces it with replace_with instead (e.g. 'tum' -> 'aap', 'yaar' -> 'Sir').
        """
        if not word_or_phrase or not str(word_or_phrase).strip():
            return "No word specified for replacement rule, Sir."

        w_orig = str(word_or_phrase).strip()
        w_repl = str(replace_with).strip() if replace_with else ""
        targets = self._resolve_target(persona)
        saved_to = []

        for rules, file_path, label in targets:
            repl_map = rules.get("word_replacements", {})
            repl_map[w_orig] = w_repl
            rules["word_replacements"] = repl_map
            self._save_file(file_path, rules)
            saved_to.append(label)

        print(f"[IgnoreWords [REPLACE] Added]: '{w_orig}' -> '{w_repl}' for {', '.join(saved_to)}")
        return f"Rule saved for {', '.join(saved_to)}: Whenever '{w_orig}' occurs, I will say '{w_repl}' instead, Sir."

    def remove_rule(self, word: str, persona: str = "auto") -> str:
        """Removes a forbidden word or replacement rule."""
        if not word or not str(word).strip():
            return "No word specified to remove, Sir."

        clean_w = str(word).strip()
        targets = self._resolve_target(persona)
        removed_from = []

        for rules, file_path, label in targets:
            # 1. Check forbidden list
            forb = rules.get("forbidden_words", [])
            new_forb = [w for w in forb if w.lower() != clean_w.lower()]
            changed = False
            if len(new_forb) != len(forb):
                rules["forbidden_words"] = new_forb
                changed = True

            # 2. Check replacements
            repl_map = rules.get("word_replacements", {})
            keys_to_del = [k for k in repl_map if k.lower() == clean_w.lower()]
            if keys_to_del:
                for k in keys_to_del:
                    del repl_map[k]
                rules["word_replacements"] = repl_map
                changed = True

            if changed:
                self._save_file(file_path, rules)
                removed_from.append(label)

        if removed_from:
            return f"Sir, '{clean_w}' rule has been removed from {', '.join(removed_from)}."
        else:
            return f"Sir, '{clean_w}' was not found in the ignore words rules for {targets[0][2]}."

    def get_forbidden_words(self, persona: str = None) -> list:
        """Returns all forbidden words for active persona + global."""
        if persona is None:
            try:
                from cwa_agent.core.speaker import speaker
                persona = getattr(speaker, 'persona', 'CWA')
            except Exception:
                persona = "CWA"

        p = str(persona).lower().strip()
        words = list(self.global_rules.get("forbidden_words", []))
        if p in ["female", "mj", "girl"]:
            words.extend(self.female_rules.get("forbidden_words", []))
        else:
            words.extend(self.male_rules.get("forbidden_words", []))

        # Return unique words preserving order
        seen = set()
        unique = []
        for w in words:
            low = w.lower().strip()
            if low and low not in seen:
                seen.add(low)
                unique.append(w.strip())
        return unique

    def get_word_replacements(self, persona: str = None) -> dict:
        """Returns active replacement mapping for active persona + global."""
        if persona is None:
            try:
                from cwa_agent.core.speaker import speaker
                persona = getattr(speaker, 'persona', 'CWA')
            except Exception:
                persona = "CWA"

        p = str(persona).lower().strip()
        merged = {}
        # Global replacements first
        merged.update(self.global_rules.get("word_replacements", {}))
        # Specific persona replacements override global
        if p in ["female", "mj", "girl"]:
            merged.update(self.female_rules.get("word_replacements", {}))
        else:
            merged.update(self.male_rules.get("word_replacements", {}))
        return merged

    def filter_and_replace_text(self, text: str, persona: str = None) -> str:
        """
        Dynamically applies all word replacement rules and censors forbidden words
        from text streams before being displayed on HUD or spoken aloud via TTS.
        """
        if not text:
            return text

        result = str(text)

        # 1. Apply Word Replacements
        replacements = self.get_word_replacements(persona)
        for orig, repl in replacements.items():
            if not orig:
                continue
            pattern = re.compile(re.escape(orig), re.IGNORECASE)
            result = pattern.sub(repl, result)

        # 2. Censor Forbidden Words
        forbidden = self.get_forbidden_words(persona)
        for forb in forbidden:
            if not forb:
                continue
            pattern = re.compile(re.escape(forb), re.IGNORECASE)
            result = pattern.sub("", result)

        # Clean up accidental double spaces
        result = re.sub(r' {2,}', ' ', result).strip()
        return result

    def list_all_rules(self) -> str:
        """Returns a formatted summary of all persona ignore rules."""
        m_forb = self.male_rules.get("forbidden_words", [])
        m_repl = self.male_rules.get("word_replacements", {})
        f_forb = self.female_rules.get("forbidden_words", [])
        f_repl = self.female_rules.get("word_replacements", {})
        g_forb = self.global_rules.get("forbidden_words", [])
        g_repl = self.global_rules.get("word_replacements", {})

        report = ["📋 PERSONA IGNORE & FORBIDDEN WORDS REGISTRY:"]

        # Male
        report.append("\n👨 MALE PERSONA (CWA / JARVIS):")
        report.append(f"  • Forbidden Words: {', '.join(m_forb) if m_forb else 'None'}")
        if m_repl:
            report.append("  • Word Replacements: " + ", ".join(f"'{k}' ➔ '{v}'" for k, v in m_repl.items()))

        # Female
        report.append("\n👩 FEMALE PERSONA (MJ):")
        report.append(f"  • Forbidden Words: {', '.join(f_forb) if f_forb else 'None'}")
        if f_repl:
            report.append("  • Word Replacements: " + ", ".join(f"'{k}' ➔ '{v}'" for k, v in f_repl.items()))

        # Global
        if g_forb or g_repl:
            report.append("\n🌐 GLOBAL (BOTH PERSONAS):")
            if g_forb:
                report.append(f"  • Forbidden Words: {', '.join(g_forb)}")
            if g_repl:
                report.append("  • Word Replacements: " + ", ".join(f"'{k}' ➔ '{v}'" for k, v in g_repl.items()))

        return "\n".join(report)

    def get_system_prompt_context(self, persona: str = None) -> str:
        """Generates dynamic instructions for Gemini on what words are banned/substituted."""
        forbidden = self.get_forbidden_words(persona)
        replacements = self.get_word_replacements(persona)

        parts = []
        if forbidden:
            parts.append(f"STRICT FORBIDDEN WORDS: Under NO circumstances are you allowed to say or write any of these words: {', '.join(forbidden)}.")
        if replacements:
            sub_rules = [f"Instead of '{k}', always say '{v}'" for k, v in replacements.items()]
            parts.append(f"PREFERRED WORD SUBSTITUTIONS: {'; '.join(sub_rules)}.")

        return "\n".join(parts)


# Singleton Instance
ignore_words_manager = IgnoreWordsManager()
