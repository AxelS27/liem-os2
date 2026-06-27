import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def run_command(cmd, check=True):
    """Runs a shell command and returns output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}\nStderr: {result.stderr}\nStdout: {result.stdout}")
        sys.exit(result.returncode)
    return result.stdout.strip(), result.returncode

def check_infinite_loop():
    """Aborts if there have been consecutive self-healing commits."""
    # Check the last 4 commits
    log, _ = run_command("git log -n 4 --oneline", check=False)
    if not log:
        return
        
    print(f"Recent Git commits:\n{log}")
    commits = log.split("\n")
    self_heal_count = sum(1 for c in commits if "[self-heal]" in c)
    
    if self_heal_count >= 3:
        print("CRITICAL: 3 or more consecutive self-heal commits detected. Aborting to prevent infinite loop.")
        sys.exit(1)

def detect_failures():
    """Checks log files to see if tests or security audits failed."""
    has_failed = False
    failure_details = []
    
    # 1. Check SkillSpector logs
    if os.path.exists("security_results.log"):
        with open("security_results.log", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # If log doesn't contain "[ok]" or contains "issues"
            if "issues" in content or "UNTRUSTED" in content or "vulnerabilit" in content:
                print("Security scan failure detected in security_results.log.")
                has_failed = True
                failure_details.append(f"=== SECURITY SCAN FAILURES ===\n{content}")
                
    # 2. Check Pytest logs
    if os.path.exists("test_results.log"):
        with open("test_results.log", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "FAIL" in content or "failed" in content or "Exception" in content or "Error" in content or "Pytest failed" in content:
                print("Test failure detected in test_results.log.")
                has_failed = True
                failure_details.append(f"=== TEST FAILURES ===\n{content}")
                
    return has_failed, "\n\n".join(failure_details)

def get_modified_files():
    """Lists all files tracked by git to help Gemini find the source of error."""
    files_str, _ = run_command("git ls-files", check=False)
    return files_str.split("\n") if files_str else []

def call_gemini(prompt):
    """Invokes Gemini API with structured JSON output request."""
    if not API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "explanation": {"type": "STRING"},
                    "files": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "path": {"type": "STRING"},
                                "content": {"type": "STRING"}
                            },
                            "required": ["path", "content"]
                        }
                    }
                },
                "required": ["explanation", "files"]
            }
        }
    }
    
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            # Parse candidate text response
            candidate_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(candidate_text)
    except urllib.error.HTTPError as e:
        print(f"Gemini API Request failed with status {e.code}: {e.read().decode('utf-8')}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to communicate with Gemini: {e}")
        sys.exit(1)

def main():
    print("Initializing Self-Healing check...")
    
    has_failed, failures = detect_failures()
    if not has_failed:
        print("Success: No test or security failures detected. Code is healthy!")
        sys.exit(0)
        
    print("Failures detected. Starting self-healing cycle...")
    check_infinite_loop()
    
    # Locate project files to include as context
    project_files = get_modified_files()
    file_contents = {}
    
    # Read files in workspace (exclude virtualenv or build directories)
    for path in project_files:
        if not path or not os.path.exists(path) or os.path.isdir(path):
            continue
        if path.startswith(".") or "venv" in path or "dist" in path or "build" in path or "node_modules" in path:
            continue
        # Only read code or markdown files (under 100KB) to stay within token limits
        if os.path.getsize(path) > 100000:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                file_contents[path] = f.read()
        except:
            pass

    # Build prompt
    prompt = f"""
You are a Self-Healing CI/CD Agent. The build, test, or security checks have failed in GitHub Actions.
Your job is to analyze the error logs, locate the bug in the files, and provide the fixed code.

=== FAILURE LOGS ===
{failures}

=== REPOSITORY FILES ===
"""
    for path, content in file_contents.items():
        prompt += f"\n--- File: {path} ---\n{content}\n"
        
    prompt += """
Please analyze the error logs and files, find the exact cause of the failures, and return the corrected files.
Provide a clear explanation of what went wrong and how you fixed it.
"""
    
    print("Requesting code fixes from Gemini API...")
    response = call_gemini(prompt)
    
    explanation = response.get("explanation", "No explanation provided.")
    fixed_files = response.get("files", [])
    
    print(f"\nGemini Audit Fix Report:\n{explanation}\n")
    
    if not fixed_files:
        print("Gemini did not propose any file fixes. Aborting.")
        sys.exit(1)
        
    # Write fixes to disk
    for file_fix in fixed_files:
        path = file_fix["path"]
        content = file_fix["content"]
        print(f"Applying patch to: {path}...")
        
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(os.path.abspath(path)) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
    # Push changes back to GitHub
    print("Committing and pushing fixed code...")
    run_command("git config --global user.name 'github-actions[bot]'")
    run_command("git config --global user.email 'github-actions[bot]@users.noreply.github.com'")
    run_command("git add .")
    
    # Determine self-healing attempt number
    log, _ = run_command("git log -n 5 --oneline", check=False)
    attempt = log.count("[self-heal]") + 1
    
    commit_msg = f"[self-heal] Attempt {attempt}: resolve test or security failures"
    run_command(f'git commit -m "{commit_msg}"')
    
    # Push back to branch using GITHUB_TOKEN or default GHA auth
    # For GHA pushes, we push HEAD to the current branch
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    run_command(f"git push origin HEAD:{branch}")
    print(f"Successfully pushed self-healing attempt {attempt} to branch {branch}!")

if __name__ == "__main__":
    main()
