import logging
import os
import sys
import requests

from src.config import SummaryConfig
from src.github_auth import GitHubAuthManager
from src.diff_parser import filter_diff_for_summary
from src.summarizer import PRSummarizer, QuotaExceededException, HighDemandException
from src.pr_updater import PRUpdater

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pr_summary")
logging.getLogger("google_genai").setLevel(logging.WARNING)


def fetch_pr_diff(pr_api_url: str, token: str, pr=None) -> str:
    """Fetches the unified diff text from GitHub API for the PR."""
    headers = {
        "Accept": "application/vnd.github.v3.diff",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(pr_api_url, headers=headers, timeout=60)
    if response.status_code == 200:
        return response.text

    if response.status_code == 406 and pr is not None:
        logger.warning("PR diff endpoint returned 406 (diff too large). Assembling from file patches...")
        patches = []
        for f in pr.get_files():
            if f.patch:
                patches.append(f"diff --git a/{f.filename} b/{f.filename}\n--- a/{f.filename}\n+++ b/{f.filename}\n{f.patch}")
        return "\n".join(patches)

    response.raise_for_status()
    return response.text


def main():
    logger.info("Starting PR Summary Writer Autonomous Engine...")

    try:
        config = SummaryConfig.from_env()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # 0. Safety Guard: Never respond to bot comments to prevent recursive feedback loops
    author_type = config.comment_author_type.lower() if isinstance(config.comment_author_type, str) else ""
    author_name = config.comment_author.lower() if isinstance(config.comment_author, str) else ""
    if author_type == "bot" or author_name.endswith("[bot]"):
        logger.info(f"Ignoring trigger from bot author '{config.comment_author}' ({config.comment_author_type}). Aborting.")
        return

    # If triggered by a comment event, ensure an explicit slash command was invoked
    if config.event_name in ("issue_comment", "pull_request_review_comment", "pull_request_review"):
        lower_body = config.comment_body.lower()
        if not ("/summarize" in lower_body or "/summary" in lower_body):
            logger.info("Comment or review body does not invoke a /summarize slash command. Nothing to do.")
            return

    # Authenticate with GitHub
    auth_manager = GitHubAuthManager(
        token=config.github_token,
        app_id=config.app_id,
        private_key=config.private_key,
    )

    target_g = auth_manager.get_client_for_repo(config.github_repository)
    repo = target_g.get_repo(config.github_repository)
    pr = repo.get_pull(config.pr_number)

    logger.info(f"Loaded PR #{pr.number}: '{pr.title}' ({pr.base.ref} <- {pr.head.ref})")

    # Acknowledge the request immediately with 👀 reaction if triggered by a comment
    target_comment = None
    if config.comment_id:
        try:
            target_comment = pr.get_issue_comment(config.comment_id)
            target_comment.create_reaction("eyes")
        except Exception:
            pass

    # Fetch raw diff via REST API
    target_token = auth_manager.get_token_for_repo(config.github_repository) or config.github_token or ""
    raw_diff = fetch_pr_diff(pr.url, target_token, pr=pr)

    # Filter diff
    filtered_diff, included_files, ignored_files = filter_diff_for_summary(raw_diff)
    logger.info(f"Diff filtered: {len(included_files)} file(s) included, {len(ignored_files)} ignored.")

    if not included_files:
        logger.info("No summarizable source files modified in this PR. Skipping summary.")
        return

    try:
        # Synthesize summary via Gemini
        summarizer = PRSummarizer(config)
        summary_markdown = summarizer.generate_summary(
            pr_title=pr.title,
            pr_base=pr.base.ref,
            pr_head=pr.head.ref,
            diff_text=filtered_diff,
            file_list=included_files,
        )

        # Update PR target
        updater = PRUpdater(pr)

        if config.target_mode in ("description", "both"):
            updater.update_description(summary_markdown)

        if config.target_mode in ("comment", "both"):
            updater.update_sticky_comment(summary_markdown)

        updater.write_step_summary(summary_markdown)

        # React with hooray reaction if triggered by a comment
        if target_comment:
            try:
                target_comment.create_reaction("hooray")
            except Exception:
                pass

        logger.info("Successfully generated and updated PR summary.")

    except QuotaExceededException as qe:
        logger.warning(f"Quota error: {qe}")
        PRUpdater(pr).write_step_summary("⚠️ **PR Summary Writer**: Skipped AI summary generation because Google Gemini API quota or rate limits are exhausted for today.")
        if target_comment:
            try:
                target_comment.create_reaction("confused")
                pr.create_issue_comment("😴 **PR Summary Writer is resting:** AI API quota or rate limit exceeded for today. Please try again later.")
            except Exception:
                pass
        sys.exit(0)
    except HighDemandException as hde:
        logger.warning(f"High demand error: {hde}")
        PRUpdater(pr).write_step_summary("⏳ **PR Summary Writer**: Skipped AI summary generation because the Gemini model is experiencing temporary high demand.")
        if target_comment:
            try:
                target_comment.create_reaction("confused")
                pr.create_issue_comment("⏳ **PR Summary Writer is busy:** The AI model is currently experiencing high demand. Please try again in a few moments.")
            except Exception:
                pass
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during summary generation: {e}", exc_info=True)
        if target_comment:
            try:
                target_comment.create_reaction("confused")
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
