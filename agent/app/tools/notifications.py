import httpx
from loguru import logger
from app.config import settings

def send_teams_rca_card(
    rca_result: dict,
    job_name: str,
    build_id: str,
    author_email: str = "",
    change_id: str = ""
) -> bool:
    """Dispatches a flat JSON payload to Power Automate for conditional routing."""
    webhook_url = settings.teams_webhook_url
    if not webhook_url:
        logger.warning("TEAMS_WEBHOOK_URL is not set. Skipping Teams notification.")
        return False

    # Extract domain and map to standard classification string
    domain_raw = str(rca_result.get("domain", "")).upper()
    failure_type = "INFRASTRUCTURE" if "INFRA" in domain_raw else "CODE"

    root_cause = rca_result.get("root_cause", "No root cause identified.")
    recommended_fix = rca_result.get("recommended_fix", "No fix recommended.")

    # Flat payload matching Power Automate Parse JSON schema
    payload = {
        "failure_type": failure_type,
        "root_cause": root_cause,
        "recommended_fix": recommended_fix,
        "author_email": author_email,
        "author_name": author_email.split("@")[0] if author_email else "Developer",
        "change_url": change_id,
        "job_name": job_name,
        "build_number": str(build_id)
    }

    try:
        response = httpx.post(
            webhook_url, 
            json=payload, 
            headers={"Content-Type": "application/json"}, 
            timeout=10.0
        )
        if response.status_code in [200, 202]:
            logger.info(f"Successfully posted RCA notification to Power Automate for build {build_id}.")
            return True
        else:
            logger.error(f"Failed to send webhook. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error dispatching webhook to Power Automate: {str(e)}")
        return False