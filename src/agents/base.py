import os
import re
from typing import Dict, Any, List

class LiemBaseAgent:
    """
    Base Agent runner.
    Parses declarative agent markdown skills (.md), extracting YAML frontmatter
    and system prompts. Simulates LLM execution with seed and temperature constraints.
    """
    def __init__(self, skill_path: str):
        self.skill_path = skill_path
        self.name = ""
        self.description = ""
        self.domain = ""
        self.tools: List[str] = []
        self.system_prompt = ""
        self._load_skill()

    def _load_skill(self) -> None:
        if not os.path.exists(self.skill_path):
            raise FileNotFoundError(f"Skill file not found at {self.skill_path}")
            
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse YAML frontmatter
        # Matches content between the first two '---' boundaries
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if match:
            frontmatter_raw = match.group(1)
            self.system_prompt = match.group(2).strip()
            self._parse_frontmatter(frontmatter_raw)
        else:
            self.system_prompt = content.strip()

    def _parse_frontmatter(self, yaml_text: str) -> None:
        # Simple manual YAML parser to avoid absolute dependency on PyYAML
        for line in yaml_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "name":
                    self.name = val
                elif key == "description":
                    self.description = val
                elif key == "domain":
                    self.domain = val
                elif key == "tools":
                    # Simple list parsing
                    pass
            elif line.startswith("-") and self.tools is not None:
                tool_name = line.strip("- ").strip('"').strip("'")
                self.tools.append(tool_name)

    def execute_inference(self, prompt: str, seed: int = 42, temperature: float = 0.7) -> str:
        """
        Simulates model inference using deterministic configurations.
        Adjusts response characteristics depending on temperature (e.g. decayed vs high).
        """
        # In a real setup, this triggers the GenAI SDK or Ollama/Llama.cpp client
        # with locked seed and temperature.
        return f"[MOCK_RESPONSE] [Seed: {seed}] [Temp: {temperature:.2f}]"
