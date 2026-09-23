def test_list_projects_includes_project_in_use(bq, project, dataset):
    assert project in [p.project_id for p in bq.list_projects()]


def test_service_account_email(bq):
    assert bq.get_service_account_email().endswith(".iam.gserviceaccount.com")
