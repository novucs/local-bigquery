from local_bigquery.api import Router, paginate
from local_bigquery.engine import database
from local_bigquery.models import GetServiceAccountResponse, ProjectList

router = Router(tags=["projects"])


@router.get("/projects")
def list_projects(
    maxResults: int | None = None, pageToken: str | None = None
) -> ProjectList:
    project_ids = database.projects()
    page, token = paginate(project_ids, maxResults, pageToken)
    return ProjectList(
        kind="bigquery#projectList",
        projects=[
            {
                "kind": "bigquery#project",
                "id": project_id,
                "numericId": str(abs(hash(project_id))),
                "friendlyName": project_id,
                "projectReference": {"projectId": project_id},
            }
            for project_id in page
        ],
        nextPageToken=token,
        totalItems=len(project_ids),
    )


@router.get("/projects/{project_id}/serviceAccount")
def get_service_account(project_id: str) -> GetServiceAccountResponse:
    return GetServiceAccountResponse(
        email=f"service-account@{project_id}.iam.gserviceaccount.com"
    )
