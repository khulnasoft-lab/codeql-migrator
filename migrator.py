import os
import requests
import subprocess
from github import Github
from typing import List, Dict, Optional, Tuple, Union
from pathlib import Path
import argparse
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import shutil
import time
import json
from datetime import datetime
from tqdm import tqdm

# Configure logging with file output
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# GitHub Token (Set this as an environment variable)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is not set")

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Enhanced default settings
DEFAULT_PER_PAGE = 10
DEFAULT_BRANCH_NAME = "update-codeql-v3"
DEFAULT_PR_TITLE = "Upgrade CodeQL Action to v3"
DEFAULT_PR_BODY = """
GitHub has deprecated CodeQL Action v2. This PR updates workflows to use CodeQL Action v3.

## Changes Made
- Updated CodeQL action versions from v2 to v3
- Ensured compatibility with latest GitHub Actions
- Added necessary configuration updates

## Migration Notes
- This update is required as v2 will be deprecated
- No breaking changes are expected
- Testing is recommended after the update

For more information, see the [CodeQL Action documentation](https://github.com/github/codeql-action)
"""

MAX_RETRIES = 5
TIMEOUT = 45
RETRY_DELAY = 5
BATCH_SIZE = 5

# Extended CodeQL action mappings
CODEQL_UPDATES = {
    "uses: github/codeql-action/init@v2": "uses: github/codeql-action/init@v3",
    "uses: github/codeql-action/analyze@v2": "uses: github/codeql-action/analyze@v3",
    "uses: github/codeql-action/autobuild@v2": "uses: github/codeql-action/autobuild@v3",
    "uses: github/codeql-action/upload-sarif@v2": "uses: github/codeql-action/upload-sarif@v3",
    "uses: github/codeql-action@v2": "uses: github/codeql-action@v3"
}

# Additional configuration options
WORKFLOW_CONFIG = {
    "supported_languages": ["cpp", "csharp", "go", "java", "javascript", "python", "ruby"],
    "default_queries": "security-extended",
    "query_suites": ["security-extended", "security-and-quality"]
}

class MigratorError(Exception):
    """Base exception for migrator errors"""
    pass

class GitHubAPIError(MigratorError):
    """Raised when GitHub API calls fail"""
    pass

class WorkflowUpdateError(MigratorError):
    """Raised when workflow updates fail"""
    pass

class ValidationError(MigratorError):
    """Raised when validation fails"""
    pass

class CleanupError(MigratorError):
    """Raised when cleanup operations fail"""
    pass

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments with extended options."""
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
        default=False,
        help="Show what would be done without making actual changes"
    )
    parser.add_argument(
        "--branch-name",
        type=str,
        default=DEFAULT_BRANCH_NAME,
        help="Name of the branch to create for the changes"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        default=False,
        help="Skip cleanup of cloned repositories"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of worker threads (default: 4)"
    )
    parser.add_argument(
        "--config-file",
        type=str,
        default=None,
        help="Path to custom configuration file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force update without prompts"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        default=False,
        help="Generate detailed migration report"
    )
    args = parser.parse_args()
    return args

def retry_with_backoff(func):
    """Enhanced decorator for retrying functions with exponential backoff and progress tracking"""
    def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.RequestException, GitHubAPIError) as e:
                if attempt == MAX_RETRIES - 1:
                    raise GitHubAPIError(f"Failed after {MAX_RETRIES} attempts: {str(e)}")
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s... Error: {str(e)}")
                time.sleep(wait_time)
        return None
    return wrapper

def generate_migration_report(results: List[Dict]) -> None:
    """Generate a detailed migration report"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_repositories": len(results),
        "successful_migrations": sum(1 for r in results if r.get("success")),
        "failed_migrations": sum(1 for r in results if not r.get("success")),
        "details": results
    }
    
    report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Migration report generated: {report_file}")

def validate_workflow_file(content: str) -> Tuple[bool, List[str]]:
    """Enhanced workflow validation with detailed checks"""
    try:
        yaml_content = yaml.safe_load(content)
        if not yaml_content:
            return False, ["Empty workflow file"]
        
        issues = []
        if "jobs" not in yaml_content:
            issues.append("No jobs defined in workflow")
        
        # Validate CodeQL-specific configurations
        for job in yaml_content.get("jobs", {}).values():
            if "steps" in job:
                for step in job["steps"]:
                    if isinstance(step, dict) and "uses" in step:
                        if "github/codeql-action" in step["uses"]:
                            if not any(lang in str(step.get("with", {})) for lang in WORKFLOW_CONFIG["supported_languages"]):
                                issues.append("No supported languages specified in CodeQL configuration")
        
        return len(issues) == 0, issues
    except yaml.YAMLError as e:
        return False, [f"Invalid YAML content: {str(e)}"]

def backup_workflow_file(filepath: Path) -> None:
    """Create backup of workflow file before modification"""
    backup_dir = filepath.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"{filepath.name}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    logger.info(f"Created backup: {backup_path}")

def process_repository(repo: Dict, args: argparse.Namespace) -> Dict[str, Union[str, bool]]:
    """Enhanced repository processing with detailed status tracking"""
    result = {
        "repository": f"{repo['repository']['owner']['login']}/{repo['repository']['name']}",
        "success": False,
        "actions_taken": [],
        "errors": [],
        "pr_url": None
    }

    repo_url = repo["repository"]["clone_url"]
    repo_name = repo["repository"]["name"]
    repo_owner = repo["repository"]["owner"]["login"]

    logger.info(f"Processing {repo_owner}/{repo_name}...")
    
    if args.dry_run:
        logger.info(f"Would clone and update {repo_name}")
        result["success"] = True
        result["actions_taken"].append("dry_run")
        return result

    try:
        clone_repo(repo_url, repo_name)
        result["actions_taken"].append("cloned")

        if find_and_update_workflows(repo_name):
            result["actions_taken"].append("workflows_updated")
            
            if args.force or prompt_user(f"Create PR for {repo_name}?"):
                pr_url = create_pull_request(
                    repo_owner,
                    repo_name,
                    args.branch_name,
                    args.dry_run
                )
                if pr_url:
                    result["pr_url"] = pr_url
                    result["success"] = True
                    result["actions_taken"].append("pr_created")
                    logger.info(f"PR Created: {pr_url}")
                else:
                    result["errors"].append("Failed to create PR")
        else:
            result["actions_taken"].append("no_updates_needed")
            logger.info(f"No updates needed for {repo_name}")
            
    except Exception as e:
        error_msg = f"Error processing {repo_name}: {str(e)}"
        result["errors"].append(error_msg)
        logger.error(error_msg)
    finally:
        if not args.skip_cleanup:
            try:
                cleanup_resources(Path(repo_name))
                result["actions_taken"].append("cleanup_completed")
            except CleanupError as e:
                result["errors"].append(f"Cleanup error: {str(e)}")
                logger.error(str(e))
    
    return result

def main() -> None:
    """Enhanced main function with progress tracking and reporting"""
    try:
        args = parse_arguments()
        start_time = time.time()
        
        logger.info("Starting CodeQL migration process...")
        repos = search_repositories(args.per_page)
        
        if not repos:
            logger.info("No repositories found using CodeQL v2.")
            return

        logger.info(f"\nFound {len(repos)} repositories to process.")
        if not args.force and not prompt_user("Do you want to continue?"):
            logger.info("Operation cancelled.")
            return

        results = []
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = []
            for repo in repos:
                future = executor.submit(process_repository, repo, args)
                futures.append(future)
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing repositories"):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error in worker thread: {str(e)}")

        if args.report:
            generate_migration_report(results)

        execution_time = time.time() - start_time
        logger.info(f"\nMigration completed in {execution_time:.2f} seconds!")
        logger.info(f"Successful migrations: {sum(1 for r in results if r['success'])}")
        logger.info(f"Failed migrations: {sum(1 for r in results if not r['success'])}")
        
    except KeyboardInterrupt:
        logger.error("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()