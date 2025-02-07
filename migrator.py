import os
import requests
import subprocess
from github import Github
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import argparse
import sys

# GitHub Token (Set this as an environment variable)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is not set")

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Default settings
DEFAULT_PER_PAGE = 10
DEFAULT_BRANCH_NAME = "update-codeql-v3"
DEFAULT_PR_TITLE = "Upgrade CodeQL Action to v3"
DEFAULT_PR_BODY = (
    "GitHub has deprecated CodeQL Action v2. "
    "This PR updates workflows to use CodeQL Action v3."
)

# GitHub API Search Query for repositories using CodeQL v2
SEARCH_QUERY = 'uses:github/codeql-action/init@v2 in:file language:YAML'

# CodeQL action mappings for version updates
CODEQL_UPDATES = {
    "uses: github/codeql-action/init@v2": "uses: github/codeql-action/init@v3",
    "uses: github/codeql-action/analyze@v2": "uses: github/codeql-action/analyze@v3",
    "uses: github/codeql-action/autobuild@v2": "uses: github/codeql-action/autobuild@v3"
}

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate GitHub repositories from CodeQL v2 to v3"
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help="Number of repositories to process (default: 10)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making actual changes"
    )
    parser.add_argument(
        "--branch-name",
        default=DEFAULT_BRANCH_NAME,
        help="Name of the branch to create for the changes"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleanup of cloned repositories"
    )
    return parser.parse_args()

def prompt_user(message: str, default: str = "y") -> bool:
    """Prompt user for yes/no confirmation."""
    valid = {"yes": True, "y": True, "no": False, "n": False}
    if default.lower() not in ("y", "n"):
        raise ValueError("Invalid default answer")
    
    prompt = " [Y/n] " if default.lower() == "y" else " [y/N] "
    while True:
        sys.stdout.write(message + prompt)
        choice = input().lower() or default.lower()
        if choice in valid:
            return valid[choice]
        sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")

def search_repositories(per_page: int = DEFAULT_PER_PAGE) -> List[Dict]:
    """Search for repositories using CodeQL v2 action."""
    url = f"https://api.github.com/search/code?q={SEARCH_QUERY}&per_page={per_page}"
    response = requests.get(url, headers=HEADERS, timeout=30).json()
    
    if "items" not in response:
        print(f"Error in API response: {response.get('message', 'Unknown error')}")
        return []
    
    return response.get("items", [])

def clone_repo(repo_url: str, repo_name: str) -> None:
    """Clone a repository to local directory."""
    subprocess.run(["git", "clone", repo_url, repo_name], check=True)

def find_and_update_workflows(repo_name: str) -> bool:
    """Find and update CodeQL workflow files in the repository."""
    workflow_dir = Path(repo_name) / ".github" / "workflows"
    if not workflow_dir.exists():
        return False

    updated = False
    for filepath in workflow_dir.glob("*.y*ml"):
        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()

        # Replace v2 with v3
        new_content = content
        for old_action, new_action in CODEQL_UPDATES.items():
            new_content = new_content.replace(old_action, new_action)

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as file:
                file.write(new_content)
            updated = True

    return updated

def create_pull_request(
    repo_owner: str,
    repo_name: str,
    branch_name: str = DEFAULT_BRANCH_NAME,
    dry_run: bool = False
) -> Optional[str]:
    """Create a pull request with the CodeQL updates."""
    if dry_run:
        print(f"Would create PR for {repo_owner}/{repo_name}")
        return None

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{repo_owner}/{repo_name}")

    # Create a new branch
    default_branch = repo.default_branch
    try:
        base_branch = repo.get_branch(default_branch)
        repo.create_git_ref(
            ref=f"refs/heads/{branch_name}", 
            sha=base_branch.commit.sha
        )
    except Exception as e:
        print(f"Error creating branch: {e}")
        return None

    # Commit updated workflow files
    workflow_dir = Path(repo_name) / ".github" / "workflows"
    for filepath in workflow_dir.glob("*.y*ml"):
        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()
        
        commit_message = "Update CodeQL to v3"
        workflow_path = f".github/workflows/{filepath.name}"
        try:
            repo.create_file(
                workflow_path,
                commit_message,
                content,
                branch=branch_name
            )
        except Exception as e:
            print(f"Error creating file {workflow_path}: {e}")
            continue

    # Create PR
    try:
        pr = repo.create_pull(
            title=DEFAULT_PR_TITLE,
            body=DEFAULT_PR_BODY,
            head=branch_name,
            base=default_branch
        )
        return pr.html_url
    except Exception as e:
        print(f"Error creating PR: {e}")
        return None

def main() -> None:
    """Main function to process repositories and create PRs."""
    args = parse_arguments()
    
    print(f"Searching for repositories using CodeQL v2...")
    repos = search_repositories(args.per_page)
    
    if not repos:
        print("No repositories found using CodeQL v2.")
        return

    print(f"\nFound {len(repos)} repositories to process.")
    if not prompt_user("Do you want to continue?"):
        print("Operation cancelled.")
        return

    for repo in repos:
        repo_url = repo["repository"]["clone_url"]
        repo_name = repo["repository"]["name"]
        repo_owner = repo["repository"]["owner"]["login"]

        print(f"\nProcessing {repo_owner}/{repo_name}...")
        
        if args.dry_run:
            print(f"Would clone and update {repo_name}")
            continue

        try:
            clone_repo(repo_url, repo_name)
            if find_and_update_workflows(repo_name):
                if prompt_user(f"Create PR for {repo_name}?"):
                    pr_url = create_pull_request(
                        repo_owner,
                        repo_name,
                        args.branch_name,
                        args.dry_run
                    )
                    if pr_url:
                        print(f"PR Created: {pr_url}")
                    else:
                        print(f"Failed to create PR for {repo_name}")
            else:
                print(f"No updates needed for {repo_name}")
        except Exception as e:
            print(f"Error processing {repo_name}: {e}")
        finally:
            if not args.skip_cleanup and os.path.exists(repo_name):
                subprocess.run(["rm", "-rf", repo_name], check=True)

    print("\nMigration completed!")

if __name__ == "__main__":
    main()
