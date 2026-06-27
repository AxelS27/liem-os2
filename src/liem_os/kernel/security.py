import os
import sys
import json
import logging
import subprocess
from typing import Dict, Any, List

logger = logging.getLogger("LiemSecurity")

def find_venv_dir() -> str:
    """Traverses upwards from CWD to locate the .venv folder."""
    cwd = os.getcwd()
    current = os.path.abspath(cwd)
    while True:
        venv_path = os.path.join(current, ".venv")
        if os.path.isdir(venv_path):
            return venv_path
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # Fallback to CWD/.venv
    return os.path.join(cwd, ".venv")

def find_skills_root() -> str:
    """Traverses upwards from CWD to locate .claude/skills or .agents/skills."""
    cwd = os.getcwd()
    current = os.path.abspath(cwd)
    while True:
        path1 = os.path.join(current, ".claude", "skills")
        path2 = os.path.join(current, ".agents", "skills")
        if os.path.isdir(path1):
            return path1
        if os.path.isdir(path2):
            return path2
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # Fallback to CWD/.claude/skills
    return os.path.join(cwd, ".claude", "skills")

class SkillSpectorScanner:
    @staticmethod
    def get_skillspector_bin() -> str:
        """Resolves the correct skillspector executable path."""
        venv_dir = find_venv_dir()
        
        # 1. Check local virtual environment Scripts directory (Windows)
        local_venv_bin = os.path.join(venv_dir, "Scripts", "skillspector.exe")
        if os.path.exists(local_venv_bin):
            return local_venv_bin
            
        # 2. Check local virtual environment bin directory (Unix)
        local_venv_bin_unix = os.path.join(venv_dir, "bin", "skillspector")
        if os.path.exists(local_venv_bin_unix):
            return local_venv_bin_unix
            
        # 3. Fallback to system PATH
        return "skillspector"

    @classmethod
    def scan_path(cls, target_path: str) -> Dict[str, Any]:
        """
        Runs NVIDIA SkillSpector scanner on the target directory/file.
        Returns a dict containing the risk score, status, recommendation, and list of findings.
        """
        abs_target = os.path.abspath(target_path)
        if not os.path.exists(abs_target):
            return {
                "status": "error",
                "risk_score": 0,
                "severity": "UNKNOWN",
                "recommendation": "ERROR",
                "findings": [],
                "error": f"Path '{target_path}' does not exist."
            }

        skillspector_bin = cls.get_skillspector_bin()
        cmd = [skillspector_bin, "scan", abs_target, "--no-llm", "--format", "json"]

        try:
            # Run the command silently
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Check if execution failed completely
            if result.returncode != 0 and not result.stdout:
                logger.error(f"SkillSpector execution failed: {result.stderr}")
                return {
                    "status": "error",
                    "risk_score": 0,
                    "severity": "UNKNOWN",
                    "recommendation": "ERROR",
                    "findings": [],
                    "error": f"Execution failed: {result.stderr.strip()}"
                }

            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Map SkillSpector JSON structure
            risk_assessment = data.get("risk_assessment", {})
            score = risk_assessment.get("score", 0)
            severity = risk_assessment.get("severity", "LOW")
            recommendation = risk_assessment.get("recommendation", "SAFE")
            
            # Map issues
            issues = data.get("issues", [])
            findings = []
            for issue in issues:
                findings.append({
                    "id": issue.get("id"),
                    "category": issue.get("category"),
                    "pattern": issue.get("pattern"),
                    "severity": issue.get("severity"),
                    "file": issue.get("location", {}).get("file"),
                    "line": issue.get("location", {}).get("start_line"),
                    "explanation": issue.get("explanation"),
                    "code_snippet": issue.get("code_snippet")
                })

            return {
                "status": "success",
                "risk_score": score,
                "severity": severity,
                "recommendation": recommendation,
                "findings": findings,
                "metrics": data.get("metrics", {})
            }

        except Exception as e:
            logger.error(f"Error executing SkillSpector: {e}")
            return {
                "status": "error",
                "risk_score": 0,
                "severity": "UNKNOWN",
                "recommendation": "ERROR",
                "findings": [],
                "error": str(e)
            }

    @classmethod
    def scan_all_skills(cls, skills_root: str = None) -> List[Dict[str, Any]]:
        """Scans all skill subdirectories in the given skills root path."""
        if not skills_root:
            skills_root = find_skills_root()
            
        results = []
        if not os.path.exists(skills_root) or not os.path.isdir(skills_root):
            logger.warning(f"Skills root directory not found: {skills_root}")
            return results

        # Find all folders containing a SKILL.md
        for entry in os.scandir(skills_root):
            if entry.is_dir():
                skill_file = os.path.join(entry.path, "SKILL.md")
                if os.path.exists(skill_file):
                    logger.info(f"Auditing security for skill: {entry.name}...")
                    report = cls.scan_path(entry.path)
                    report["skill_name"] = entry.name
                    report["path"] = entry.path
                    results.append(report)
                    
        return results
