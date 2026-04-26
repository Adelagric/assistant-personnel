"""Monitoring de repos GitHub — PRs, issues, CI."""
import os
import requests


_GH_API = "https://api.github.com"


def _headers():
    token = os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def get_repo_status(owner: str, repo: str) -> dict:
    """Récupère le statut global d'un repo : PRs ouvertes, issues, dernière CI."""
    try:
        # PRs ouvertes
        prs = requests.get(
            f"{_GH_API}/repos/{owner}/{repo}/pulls",
            headers=_headers(), params={"state": "open", "per_page": 10}, timeout=10
        ).json()
        pr_list = [
            {"number": p["number"], "title": p["title"], "author": p["user"]["login"],
             "created": p["created_at"][:10], "draft": p.get("draft", False)}
            for p in (prs if isinstance(prs, list) else [])
        ]

        # Issues ouvertes récentes
        issues = requests.get(
            f"{_GH_API}/repos/{owner}/{repo}/issues",
            headers=_headers(), params={"state": "open", "per_page": 10, "sort": "created"}, timeout=10
        ).json()
        issue_list = [
            {"number": i["number"], "title": i["title"], "author": i["user"]["login"],
             "labels": [l["name"] for l in i.get("labels", [])]}
            for i in (issues if isinstance(issues, list) else [])
            if "pull_request" not in i  # exclure les PRs
        ]

        # Dernier workflow run
        runs_resp = requests.get(
            f"{_GH_API}/repos/{owner}/{repo}/actions/runs",
            headers=_headers(), params={"per_page": 3}, timeout=10
        )
        ci_runs = []
        if runs_resp.status_code == 200:
            for run in runs_resp.json().get("workflow_runs", [])[:3]:
                ci_runs.append({
                    "name": run["name"],
                    "status": run["status"],
                    "conclusion": run.get("conclusion", ""),
                    "branch": run["head_branch"],
                    "date": run["created_at"][:16],
                })

        return {
            "repo": f"{owner}/{repo}",
            "open_prs": pr_list,
            "open_issues": issue_list,
            "recent_ci": ci_runs,
        }
    except Exception as e:
        return {"error": str(e)}


def list_notifications() -> list:
    """Liste les notifications GitHub non lues."""
    try:
        resp = requests.get(
            f"{_GH_API}/notifications",
            headers=_headers(), params={"all": "false"}, timeout=10
        )
        if resp.status_code != 200:
            return [{"error": f"HTTP {resp.status_code} — GITHUB_TOKEN peut-être manquant"}]
        notifs = []
        for n in resp.json()[:15]:
            notifs.append({
                "repo": n["repository"]["full_name"],
                "type": n["subject"]["type"],
                "title": n["subject"]["title"],
                "reason": n["reason"],
                "updated": n["updated_at"][:16],
            })
        return notifs
    except Exception as e:
        return [{"error": str(e)}]
