import os
import time
import requests
import json
import uuid
import zipfile
import io
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class GitHubRestartWorkflowManager:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO")
        
        if not self.github_token:
            raise ValueError("GitHub token not configured")
        if not self.github_repo:
            raise ValueError("GitHub repository not configured")
            
        print(f"Using GitHub token: {self.github_token[:5]}... (last 5 chars shown for security)")
        print(f"Using GitHub repository: {self.github_repo}")

    def trigger_restart_workflow(self, app_name: str, unique_id: str) -> None:
        """Triggers the restart workflow and returns immediately"""
        response = requests.post(
            f"https://api.github.com/repos/{self.github_repo}/actions/workflows/trialrestart.yml/dispatches",
            headers={
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            json={
                "ref": "main",
                "inputs": {
                    "container_app_name": app_name,
                    "unique_id": unique_id
                }
            }
        )
        if response.status_code != 204:
            raise Exception(f"Failed to trigger workflow: {response.status_code} - {response.text}")

    def get_workflow_run_by_artifact(self, unique_id: str, timeout: int = 300) -> int:
        """Finds the workflow run by scanning artifacts for a specific unique_id."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            runs = requests.get(
                f"https://api.github.com/repos/{self.github_repo}/actions/workflows/trialrestart.yml/runs",
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github+json"
                },
                params={"per_page": 10}
            ).json().get("workflow_runs", [])

            for run in runs:
                if run["status"] != "completed":
                    continue

                artifacts = requests.get(
                    f"https://api.github.com/repos/{self.github_repo}/actions/runs/{run['id']}/artifacts",
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github+json"
                    }
                ).json().get("artifacts", [])

                for artifact in artifacts:
                    if artifact["name"] == f"result_{unique_id}":
                        return run["id"]

            time.sleep(10)

        raise TimeoutError("Could not find workflow run with the specified unique_id artifact.")

    def download_and_verify_artifact(self, run_id: int, app_name: str, unique_id: str) -> Dict[str, Any]:
        """Downloads and verifies the specific artifact."""
        artifact_url = f"https://api.github.com/repos/{self.github_repo}/actions/runs/{run_id}/artifacts"
        artifacts = requests.get(
            artifact_url,
            headers={"Authorization": f"token {self.github_token}", "Accept": "application/vnd.github+json"}
        ).json().get("artifacts", [])

        artifact_name = f"result_{unique_id}"
        artifact = next((a for a in artifacts if a["name"] == artifact_name), None)
        if not artifact:
            raise Exception(f"Artifact {artifact_name} not found.")

        # Download and extract artifact
        download_url = artifact["archive_download_url"]
        response = requests.get(
            download_url,
            headers={"Authorization": f"token {self.github_token}"},
            stream=True
        )

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            result_file = f"{artifact_name}.json"
            if result_file not in z.namelist():
                raise Exception(f"Result file {result_file} not found in artifact.")

            result_content = z.read(result_file)
            result_data = json.loads(result_content)
            return result_data
