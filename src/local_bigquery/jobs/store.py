import json

from local_bigquery.engine.database import execute, fetch


def save(job: dict) -> dict:
    reference = job["jobReference"]
    execute(
        "INSERT OR REPLACE INTO emulator.jobs VALUES (?, ?, ?, ?, ?, ?)",
        [
            reference["projectId"],
            reference["jobId"],
            job["statistics"].get("parentJobId"),
            job["status"]["state"],
            int(job["statistics"]["creationTime"]),
            json.dumps(job),
        ],
    )
    return job


def load(project_id: str, job_id: str) -> dict | None:
    rows = fetch(
        "SELECT resource FROM emulator.jobs WHERE project_id = ? AND job_id = ?",
        [project_id, job_id],
    )
    return json.loads(rows[0][0]) if rows else None


def list_(
    project_id: str,
    states: list[str] | None = None,
    parent_job_id: str | None = None,
    min_creation_time: int | None = None,
    max_creation_time: int | None = None,
) -> list[dict]:
    rows = fetch(
        "SELECT resource FROM emulator.jobs WHERE project_id = ? "
        "AND parent_job_id IS NOT DISTINCT FROM ? "
        "AND (? IS NULL OR list_contains(?, state)) "
        "AND creation_time >= coalesce(?, creation_time) "
        "AND creation_time <= coalesce(?, creation_time) "
        "ORDER BY creation_time DESC, job_id",
        [
            project_id,
            parent_job_id,
            states,
            states,
            min_creation_time,
            max_creation_time,
        ],
    )
    return [json.loads(resource) for (resource,) in rows]


def delete(project_id: str, job_id: str):
    execute(
        "DELETE FROM emulator.jobs WHERE project_id = ? "
        "AND (job_id = ? OR parent_job_id = ?)",
        [project_id, job_id, job_id],
    )
