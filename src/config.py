import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SummaryConfig:
    gemini_api_key: str
    github_repository: str
    pr_number: int
    github_token: Optional[str] = None
    app_id: Optional[str] = None
    private_key: Optional[str] = None
    comment_id: Optional[int] = None
    comment_body: str = ""
    comment_author: str = ""
    comment_author_type: str = ""
    model_name: str = "auto"
    thinking_budget: int = 0
    target_mode: str = "description"  # "description", "comment", or "both"
    event_name: str = ""

    @classmethod
    def from_env(cls) -> "SummaryConfig":
        # Resolve GitHub authentication credentials
        github_token = os.environ.get("GITHUB_TOKEN", "").strip() or None
        app_id = os.environ.get("APP_ID", "").strip() or None
        private_key = os.environ.get("PRIVATE_KEY", "").strip() or None

        if not github_token and not (app_id and private_key):
            raise ValueError("Must provide either GITHUB_TOKEN or both APP_ID and PRIVATE_KEY.")

        # Resolve Gemini API Key (checking specific keys before generic fallback)
        gemini_api_key = (
            os.environ.get("PR_SUMMARY_WRITER_API_KEY", "").strip()
            or os.environ.get("PR_SUMMARIZER_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
        if not gemini_api_key:
            raise ValueError("Missing Gemini API Key. Provide PR_SUMMARY_WRITER_API_KEY or GEMINI_API_KEY.")

        github_repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        pr_number_str = os.environ.get("PR_NUMBER", "").strip()
        pr_number = int(pr_number_str) if pr_number_str.isdigit() else 0

        comment_id_str = os.environ.get("COMMENT_ID", "").strip()
        comment_id = int(comment_id_str) if comment_id_str.isdigit() else None
        comment_body = os.environ.get("COMMENT_BODY", "").strip()
        comment_author = os.environ.get("COMMENT_AUTHOR", "").strip()
        comment_author_type = os.environ.get("COMMENT_AUTHOR_TYPE", "").strip()
        event_name = os.environ.get("EVENT_NAME", "").strip()

        # Ingest GITHUB_EVENT_PATH for unescaped, accurate event payloads if available
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if event_path and os.path.isfile(event_path):
            try:
                with open(event_path, "r", encoding="utf-8") as f:
                    event_data = json.load(f)

                if not github_repository and "repository" in event_data:
                    github_repository = event_data["repository"].get("full_name", "")

                if not pr_number:
                    if "pull_request" in event_data:
                        pr_number = event_data["pull_request"].get("number", 0)
                    elif "issue" in event_data and "pull_request" in event_data["issue"]:
                        pr_number = event_data["issue"].get("number", 0)

                if "comment" in event_data:
                    comment = event_data["comment"]
                    if not comment_id:
                        comment_id = comment.get("id")
                    if not comment_body:
                        comment_body = comment.get("body", "")
                    if "user" in comment:
                        if not comment_author:
                            comment_author = comment["user"].get("login", "")
                        if not comment_author_type:
                            comment_author_type = comment["user"].get("type", "")
                elif "review" in event_data:
                    review = event_data["review"]
                    if not comment_body:
                        comment_body = review.get("body", "")
                    if "user" in review:
                        if not comment_author:
                            comment_author = review["user"].get("login", "")
                        if not comment_author_type:
                            comment_author_type = review["user"].get("type", "")

            except Exception:
                pass

        if not github_repository:
            raise ValueError("Missing GITHUB_REPOSITORY environment variable.")
        if pr_number <= 0:
            raise ValueError(f"Invalid or missing PR_NUMBER environment variable: '{pr_number_str}'")

        model_name = os.environ.get("MODEL_NAME", "auto").strip() or "auto"
        thinking_budget_str = os.environ.get("THINKING_BUDGET", "0").strip().lower()
        if thinking_budget_str in ("0", "off", "false", "none", "disable", "disabled", ""):
            thinking_budget = 0
        elif thinking_budget_str.isdigit():
            thinking_budget = int(thinking_budget_str)
        else:
            thinking_budget = 0

        target_mode = os.environ.get("TARGET_MODE", "description").strip().lower()
        if target_mode not in ("description", "comment", "both"):
            target_mode = "description"

        return cls(
            gemini_api_key=gemini_api_key,
            github_repository=github_repository,
            pr_number=pr_number,
            github_token=github_token,
            app_id=app_id,
            private_key=private_key,
            comment_id=comment_id,
            comment_body=comment_body,
            comment_author=comment_author,
            comment_author_type=comment_author_type,
            model_name=model_name,
            thinking_budget=thinking_budget,
            target_mode=target_mode,
            event_name=event_name,
        )
