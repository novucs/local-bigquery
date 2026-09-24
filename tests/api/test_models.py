import pytest
from google.api_core.exceptions import (
    Conflict,
    GoogleAPICallError,
    NotFound,
    PreconditionFailed,
)
from google.cloud import bigquery

from tests.cases import FAST_RETRY, fails, reason_and_message, run, run_job, unique

TRAINING = "SELECT 1.5 AS x, 'a' AS s, 2.0 AS label"
pytestmark = pytest.mark.emulator("BigQuery ML trains models, which is slow and billed")


@pytest.fixture
def model_id(dataset):
    return f"{dataset.project}.{dataset.dataset_id}.{unique('m')}"


def create(bq, model_id, options="model_type = 'linear_reg'", verb="CREATE MODEL"):
    return run_job(bq, f"{verb} `{model_id}` OPTIONS ({options}) AS {TRAINING}")


def test_create_model(bq, dataset, model_id):
    job = create(
        bq,
        model_id,
        "model_type = 'LINEAR_REG', labels = [('k', 'v')]",
    )
    assert job.statement_type == "CREATE_MODEL"
    model = bq.get_model(model_id, retry=FAST_RETRY)
    assert (model.model_type, model.labels) == ("LINEAR_REG", {"k": "v"})
    assert model.created and model.modified and model.etag
    assert [(f.name, f.type.type_kind) for f in model.feature_columns] == [
        ("x", "FLOAT64"),
        ("s", "STRING"),
    ]
    assert [f.name for f in model.label_columns] == ["label"]
    listed = bq.list_models(dataset, retry=FAST_RETRY)
    assert model_id.rsplit(".", 1)[1] in [m.model_id for m in listed]


def test_input_label_cols(bq, model_id):
    options = "model_type = 'logistic_reg', input_label_cols = ['s']"
    run_job(
        bq,
        f"CREATE MODEL `{model_id}` OPTIONS ({options}) AS SELECT 1.5 AS x, 'a' AS s",
    )
    model = bq.get_model(model_id, retry=FAST_RETRY)
    assert [f.name for f in model.label_columns] == ["s"]
    assert [f.name for f in model.feature_columns] == ["x"]


@pytest.mark.parametrize(
    "options, message",
    [
        (
            "model_type = 'linear_reg', description = 'd'",
            "unsupported option description",
        ),
        (
            "model_type = 'logistic_reg', input_label_cols = ['s']",
            "Column 'label' is a reserved column name for the model type LOGISTIC_REG",
        ),
    ],
)
def test_invalid_model_options(bq, model_id, options, message):
    with pytest.raises(GoogleAPICallError, match=message):
        create(bq, model_id, options)


def test_create_existing_model(bq, model_id):
    create(bq, model_id)
    with fails(Conflict, "duplicate"):
        create(bq, model_id)
    create(bq, model_id, "model_type = 'kmeans'", "CREATE MODEL IF NOT EXISTS")
    assert bq.get_model(model_id, retry=FAST_RETRY).model_type == "LINEAR_REG"
    create(bq, model_id, "model_type = 'kmeans'", "CREATE OR REPLACE MODEL")
    assert bq.get_model(model_id, retry=FAST_RETRY).model_type == "KMEANS"


def test_drop_model(bq, model_id):
    create(bq, model_id)
    assert run_job(bq, f"DROP MODEL `{model_id}`").statement_type == "DROP_MODEL"
    with fails(NotFound, "notFound"):
        bq.get_model(model_id, retry=FAST_RETRY)
    run_job(bq, f"DROP MODEL IF EXISTS `{model_id}`")
    with fails(NotFound, "notFound"):
        run_job(bq, f"DROP MODEL `{model_id}`")


def test_update_model(bq, model_id):
    create(bq, model_id)
    model = bq.get_model(model_id, retry=FAST_RETRY)
    model.description = "new"
    model.labels = {"a": "b"}
    updated = bq.update_model(model, ["description", "labels"], retry=FAST_RETRY)
    assert (updated.description, updated.labels) == ("new", {"a": "b"})
    assert updated.model_type == "LINEAR_REG"
    with fails(PreconditionFailed, "conditionNotMet"):
        bq.update_model(model, ["description"], retry=FAST_RETRY)


def test_delete_model(bq, model_id):
    create(bq, model_id)
    bq.delete_model(model_id, retry=FAST_RETRY)
    with fails(NotFound, "notFound"):
        bq.delete_model(model_id, retry=FAST_RETRY)
    bq.delete_model(model_id, not_found_ok=True, retry=FAST_RETRY)


def test_create_model_in_missing_dataset(bq, project):
    with fails(NotFound, "notFound"):
        create(bq, f"{project}.{unique('missing')}.m")


def test_models_are_dropped_with_dataset(bq, project):
    dataset_id = unique("models")
    bq.create_dataset(dataset_id, retry=FAST_RETRY)
    create(bq, f"{project}.{dataset_id}.m")
    bq.delete_dataset(dataset_id, delete_contents=True, retry=FAST_RETRY)
    bq.create_dataset(dataset_id, retry=FAST_RETRY)
    assert list(bq.list_models(dataset_id, retry=FAST_RETRY)) == []
    bq.delete_dataset(dataset_id, retry=FAST_RETRY)


@pytest.mark.parametrize(
    "call",
    [
        "ML.PREDICT(MODEL {m}, (SELECT 1.5 AS x))",
        "ML.EVALUATE(MODEL {m})",
        "ML.TRAINING_INFO(MODEL {m})",
    ],
)
def test_ml_functions_are_not_implemented(bq, dataset, model_id, call):
    create(bq, model_id)
    sql = f"SELECT * FROM {call.format(m=f'`{model_id}`')}"
    with pytest.raises(GoogleAPICallError) as info:
        run(bq, sql)
    message = reason_and_message(info.value)
    assert "notImplemented" in message and "ML." in message, message


def test_model_dry_run_does_not_create(bq, model_id):
    config = bigquery.QueryJobConfig(dry_run=True)
    sql = f"CREATE MODEL `{model_id}` OPTIONS (model_type = 'kmeans') AS {TRAINING}"
    bq.query(sql, job_config=config, retry=FAST_RETRY, job_retry=None)
    with fails(NotFound, "notFound"):
        bq.get_model(model_id, retry=FAST_RETRY)
