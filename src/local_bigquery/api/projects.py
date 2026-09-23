from local_bigquery import db
from local_bigquery.api import Router
from local_bigquery.models import GetServiceAccountResponse, ProjectList

router = Router(tags=["projects"])


@router.get("/projects")
def list_projects() -> ProjectList:
    projects = db.list_projects()
    return ProjectList(projects=projects, totalItems=len(projects))


@router.get("/projects/{project_id}/serviceAccount")
def get_service_account(project_id: str) -> GetServiceAccountResponse:
    return GetServiceAccountResponse(
        email=f"service-account@{project_id}.iam.gserviceaccount.com"
    )
