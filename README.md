# 🚀 CodeQL Migrator

**Automate the migration of CodeQL Action from v2 to v3 across GitHub repositories.**

## ❓ Why CodeQL Migrator?
GitHub has **deprecated CodeQL Action v2**, and workflows using it may eventually break. This tool:
- **Finds repositories** still using CodeQL v2.
- **Automatically updates workflows** to CodeQL v3.
- **Creates pull requests** to suggest upgrades.

## 📌 Features
✅ Scans repositories for CodeQL v2 usage.  
✅ Updates workflow files to use CodeQL v3.  
✅ Creates pull requests with upgrade suggestions.  
✅ Works on public and private repositories.  
✅ Can be run manually or as a GitHub Action.  

## 🚀 Getting Started

### 1️⃣ Clone the Repository
```sh
git clone https://github.com/YOUR-USERNAME/codeql-migrator.git
cd codeql-migrator
```

### 2️⃣ Install Dependencies
```sh
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Set Up GitHub Token
Create a **GitHub Personal Access Token (PAT)** with `repo` and `workflow` permissions.  
Set it as an environment variable:
```sh
export GITHUB_TOKEN="your_personal_access_token"
```

### 4️⃣ Run the Migration Script
```sh
python migrator.py
```

## 🛠 Automate with GitHub Actions
You can schedule automated runs with GitHub Actions.  
Create `.github/workflows/run-migrator.yml`:
```yaml
name: Run CodeQL Migrator
on:
  schedule:
    - cron: '0 0 * * 1'  # Runs every Monday
  workflow_dispatch:  # Allows manual triggering
jobs:
  run-script:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.x'

      - name: Install Dependencies
        run: pip install requests pyyaml github3.py

      - name: Run Migration Script
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python migrator.py
```

## 🛠 Using as a GitHub Action

Add this workflow to your repository to automatically migrate CodeQL from v2 to v3:

:/.github/workflows/codeql-migration.yml
name: CodeQL Migration
on:
  schedule:
    - cron: '0 0 * * 1'  # Runs every Monday
  workflow_dispatch:

jobs:
  migrate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: khulnasoft-lab/codeql-migrator@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}



### Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `github-token` | GitHub token for authentication | Yes | - |
| `per-page` | Number of repositories to process | No | '10' |
| `dry-run` | Show what would be done without making changes | No | 'false' |
| `branch-name` | Name of the branch to create for changes | No | 'update-codeql-v3' |
| `skip-cleanup` | Skip cleanup of cloned repositories | No | 'false' |
| `max-workers` | Number of concurrent workers | No | '4' |
| `log-level` | Logging verbosity | No | 'INFO' |
| `commit-message` | Commit message for the changes | No | 'Update CodeQL action to v3' |
| `pr-title` | Title for the pull request | No | 'Update CodeQL action from v2 to v3' |
| `pr-body` | Body text for the pull request | No | 'This PR updates the CodeQL action from v2 to v3.' |

## 📖 How It Works
1️⃣ **Finds repos** using CodeQL v2 via GitHub API.  
2️⃣ **Clones the repo** and checks workflow files.  
3️⃣ **Replaces** `uses: github/codeql-action/*@v2` with `@v3`.  
4️⃣ **Commits changes & creates a pull request**.  

## 🛡 Security Considerations
- The script **does not store credentials**.
- Uses GitHub API **rate-limits apply**.
- **Verify pull requests** before merging.

## 💡 Roadmap
- [ ] Add CLI options for manual repo input.
- [ ] Improve logging and error handling.
- [ ] Turn into a GitHub App for automatic suggestions.

## 🤝 Contributing
PRs are welcome! Follow the standard GitHub workflow:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit changes (`git commit -m "Add new feature"`).
4. Push to your branch (`git push origin feature-name`).
5. Open a pull request.

## 📜 License
Licensed under the **MIT License**.

## ⭐ Star This Repo!
If this project helps you, give it a ⭐ on GitHub!

## 🐳 Docker Usage

The tool is available as a Docker image from GitHub Container Registry:

```sh
docker pull ghcr.io/khulnasoft-lab/codeql-migrator:latest
```

Run it with your GitHub token:

```sh
docker run -e GITHUB_TOKEN="your_token" ghcr.io/khulnasoft-lab/codeql-migrator:latest
```

You can also use it with additional parameters:

```sh
docker run -e GITHUB_TOKEN="your_token" ghcr.io/khulnasoft-lab/codeql-migrator:latest \
  --per-page 20 \
  --dry-run \
  --branch-name custom-branch
```

---
🔥 **Automate your CodeQL upgrades today!** 🔥

