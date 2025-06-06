import os
import time
import requests
import json
import uuid
import zipfile
import io
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import re

load_dotenv()

class GitHubDeployWorkflowManager:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO")
        
        if not self.github_token:
            raise ValueError("GitHub token not configured")
        if not self.github_repo:
            raise ValueError("GitHub repository not configured")
            
        print(f"Using GitHub token: {self.github_token[:5]}... (last 5 chars shown for security)")
        print(f"Using GitHub repository: {self.github_repo}")

    def trigger_github_workflow(self, deployment_id: str, tool_dir: str, credentials: Dict[str, str], unique_id: str) -> int:
        """Triggers the deploy workflow and returns the run ID"""
        token = os.environ.get("PERSONAL_GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GitHub token not found in environment variable: PERSONAL_GITHUB_TOKEN")
        url = f"https://api.github.com/repos/adiityaaa19/custom-code/actions/workflows/admin-to-user-market-key2.yml/dispatches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
        inputs = {
            "deployment_id": deployment_id,
            "tool_dir": tool_dir,
            "credentials": json.dumps(credentials),
            "unique_id": unique_id
        }
        data = {"ref": "main", "inputs": inputs}
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        print("Workflow triggered successfully.")
        time.sleep(10)
        return self.poll_workflow_run(token)

    def poll_workflow_run(self, token: str, poll_interval: int = 10, timeout: int = 600) -> Optional[int]:
        """Poll workflow run status"""
        url = f"https://api.github.com/repos/adiityaaa19/custom-code/actions/workflows/admin-to-user-market-key2.yml/runs"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
        start_time = time.time()
        while True:
            resp = requests.get(url, headers=headers, params={"branch": "main", "event": "workflow_dispatch"})
            resp.raise_for_status()
            runs = resp.json().get("workflow_runs", [])
            if runs:
                latest_run = runs[0]
                run_id = latest_run["id"]
                status = latest_run["status"]
                conclusion = latest_run["conclusion"]
                print(f"Workflow run status: {status} (conclusion: {conclusion})")
                if status == "completed":
                    if conclusion == "success":
                        print("Workflow completed successfully.")
                        return run_id
                    else:
                        print("Workflow failed.")
                        return None
            if time.time() - start_time > timeout:
                raise TimeoutError("Timed out waiting for workflow to complete.")
            time.sleep(poll_interval)

    def download_deployed_url_artifact(self, run_id: int, deployment_id: str) -> Optional[str]:
        """Download deployment artifact and extract endpoint URL"""
        token = os.environ.get("PERSONAL_GITHUB_TOKEN")
        if not token:
            return None
            
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
        url = f"https://api.github.com/repos/adiityaaa19/custom-code/actions/runs/{run_id}/artifacts"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        artifacts = resp.json().get("artifacts", [])
        artifact_id = None
        for artifact in artifacts:
            if deployment_id in artifact["name"]:
                artifact_id = artifact["id"]
                break
        if not artifact_id:
            return None

        download_url = f"https://api.github.com/repos/adiityaaa19/custom-code/actions/artifacts/{artifact_id}/zip"
        resp = requests.get(download_url, headers=headers)
        resp.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        endpoint = ''
        for name in z.namelist():
            if name.endswith('.txt'):
                with z.open(name) as f:
                    url_content = f.read().decode()
                    match = re.search(r'https?://[\w.-]+(?:/\w+)*', url_content)
                    if match:
                        endpoint = match.group(0)
        return endpoint

    def download_and_verify_artifact(self, run_id: int, deployment_id: str, unique_id: str) -> Dict[str, Any]:
        """Downloads and verifies the specific artifact and returns the JSON result."""
        token = os.environ.get("PERSONAL_GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GitHub token not found")

        artifact_url = f"https://api.github.com/repos/adiityaaa19/custom-code/actions/runs/{run_id}/artifacts"
        artifacts = requests.get(
            artifact_url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json"
            }
        ).json().get("artifacts", [])

        artifact_name = f"result_{unique_id}"
        artifact = next((a for a in artifacts if a["name"] == artifact_name), None)
        if not artifact:
            raise Exception(f"Artifact {artifact_name} not found.")

        download_url = artifact["archive_download_url"]
        response = requests.get(
            download_url,
            headers={"Authorization": f"token {token}"},
            stream=True
        )

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            result_file = f"{artifact_name}.json"
            if result_file not in z.namelist():
                raise Exception(f"{result_file} not found in artifact.")
            with z.open(result_file) as f:
                result = json.load(f)
                # Optionally verify deployment_id matches
                if result.get("deployment_id") != deployment_id:
                    raise Exception(f"Deployment ID mismatch. Expected {deployment_id}, got {result.get('deployment_id')}")
                return result
