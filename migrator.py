import os
import requests
import yaml
import subprocess
from github import Github

# GitHub Token (Set this as an environment variable)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# GitHub API Search Query for repositories using CodeQL v2
SEARCH_QUERY = 'uses:github/codeql-action/init@v2 in:file language:YAML'

def search_repositories():
    url = f"https://api.github.com/search/code?q={SEARCH_QUERY}&per_page=10"
    response = requests.get(url, headers=HEADERS).json()
    return response.get("items", [])

def clone_repo(repo_url, repo_name):
    subprocess.run(["git", "clone", repo_url, repo_name], check=True)

def find_and_update_workflows(repo_name):
    workflow_dir = f"{repo_name}/.github/workflows/"
    if not os.path.exists(workflow_dir):
        return False

    updated = False
    for filename in os.listdir(workflow_dir):
        if filename.endswith(".yml") or filename.endswith(".yaml"):
            filepath = os.path.join(workflow_dir, filename)
            with open(filepath, "r") as file:
                content = file.read()

            # Replace v2 with v3
            new_content = content.replace("uses: github/codeql-action/init@v2", "uses: github/codeql-action/init@v3") \
                                 .replace("uses: github/codeql-action/analyze@v2", "uses: github/codeql-action/analyze@v3") \
                                 .replace("uses: github/codeql-action/autobuild@v2", "uses: github/codeql-action/autobuild@v3")

            if new_content != content:
                with open(filepath, "w") as file:
                    file.write(new_content)
                updated = True

    return updated

def create_pull_request(repo_owner, repo_name):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{repo_owner}/{repo_name}")

    # Create a new branch
    branch_name = "update-codeql-v3"
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=repo.get_branch("main").commit.sha)

    # Commit updated workflow files
    workflow_dir = f"{repo_name}/.github/workflows/"
    for filename in os.listdir(workflow_dir):
        if filename.endswith(".yml") or filename.endswith(".yaml"):
            filepath = os.path.join(workflow_dir, filename)
            with open(filepath, "r") as file:
                content = file.read()
            repo.create_file(f".github/workflows/{filename}", f"Update CodeQL to v3", content, branch=branch_name)

    # Create PR
    pr = repo.create_pull(title="Upgrade CodeQL Action to v3",
                          body="GitHub has deprecated CodeQL Action v2. This PR updates workflows to use CodeQL Action v3.",
                          head=branch_name,
                          base="main")
    print(f"PR Created: {pr.html_url}")

def main():
    repos = search_repositories()
    for repo in repos:
        repo_url = repo["repository"]["clone_url"]
        repo_name = repo["repository"]["name"]
        repo_owner = repo["repository"]["owner"]["login"]

        print(f"Processing {repo_name}...")

        try:
            clone_repo(repo_url, repo_name)
            if find_and_update_workflows(repo_name):
                create_pull_request(repo_owner, repo_name)
            else:
                print(f"No updates needed for {repo_name}.")
        except Exception as e:
            print(f"Error processing {repo_name}: {e}")

if __name__ == "__main__":
    main()
