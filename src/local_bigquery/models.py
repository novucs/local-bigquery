from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import AwareDatetime, BaseModel, Field, RootModel, constr


class AggregateClassificationMetrics(BaseModel):
    accuracy: Optional[float] = Field(
        None,
        description="Accuracy is the fraction of predictions given the correct label. For multiclass this is a micro-averaged metric.",
    )
    f1Score: Optional[float] = Field(
        None,
        description="The F1 score is an average of recall and precision. For multiclass this is a macro-averaged metric.",
    )
    logLoss: Optional[float] = Field(
        None,
        description="Logarithmic Loss. For multiclass this is a macro-averaged metric.",
    )
    precision: Optional[float] = Field(
        None,
        description="Precision is the fraction of actual positive predictions that had positive actual labels. For multiclass this is a macro-averaged metric treating each class as a binary classifier.",
    )
    recall: Optional[float] = Field(
        None,
        description="Recall is the fraction of actual positive labels that were given a positive prediction. For multiclass this is a macro-averaged metric.",
    )
    rocAuc: Optional[float] = Field(
        None,
        description="Area Under a ROC Curve. For multiclass this is a macro-averaged metric.",
    )
    threshold: Optional[float] = Field(
        None,
        description="Threshold at which the metrics are computed. For binary classification models this is the positive class threshold. For multi-class classification models this is the confidence threshold.",
    )


class AggregationThresholdPolicy(BaseModel):
    privacyUnitColumns: Optional[List[str]] = Field(
        None,
        description='Optional. The privacy unit column(s) associated with this policy. For now, only one column per data source object (table, view) is allowed as a privacy unit column. Representing as a repeated field in metadata for extensibility to multiple columns in future. Duplicates and Repeated struct fields are not allowed. For nested fields, use dot notation ("outer.inner")',
    )
    threshold: Optional[str] = Field(
        None,
        description='Optional. The threshold for the "aggregation threshold" policy.',
    )


class ArgumentKind(Enum):
    ARGUMENT_KIND_UNSPECIFIED = "ARGUMENT_KIND_UNSPECIFIED"
    FIXED_TYPE = "FIXED_TYPE"
    ANY_TYPE = "ANY_TYPE"


class Mode(Enum):
    MODE_UNSPECIFIED = "MODE_UNSPECIFIED"
    IN = "IN"
    OUT = "OUT"
    INOUT = "INOUT"


class ArimaCoefficients(BaseModel):
    autoRegressiveCoefficients: Optional[List[float]] = Field(
        None, description="Auto-regressive coefficients, an array of double."
    )
    interceptCoefficient: Optional[float] = Field(
        None, description="Intercept coefficient, just a double not an array."
    )
    movingAverageCoefficients: Optional[List[float]] = Field(
        None, description="Moving-average coefficients, an array of double."
    )


class ArimaFittingMetrics(BaseModel):
    aic: Optional[float] = Field(None, description="AIC.")
    logLikelihood: Optional[float] = Field(None, description="Log-likelihood.")
    variance: Optional[float] = Field(None, description="Variance.")


class SeasonalPeriod(Enum):
    SEASONAL_PERIOD_TYPE_UNSPECIFIED = "SEASONAL_PERIOD_TYPE_UNSPECIFIED"
    NO_SEASONALITY = "NO_SEASONALITY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"


class ArimaOrder(BaseModel):
    d: Optional[str] = Field(None, description="Order of the differencing part.")
    p: Optional[str] = Field(None, description="Order of the autoregressive part.")
    q: Optional[str] = Field(None, description="Order of the moving-average part.")


class ArimaSingleModelForecastingMetrics(BaseModel):
    arimaFittingMetrics: Optional[ArimaFittingMetrics] = Field(
        None, description="Arima fitting metrics."
    )
    hasDrift: Optional[bool] = Field(
        None,
        description="Is arima model fitted with drift or not. It is always false when d is not 1.",
    )
    hasHolidayEffect: Optional[bool] = Field(
        None,
        description="If true, holiday_effect is a part of time series decomposition result.",
    )
    hasSpikesAndDips: Optional[bool] = Field(
        None,
        description="If true, spikes_and_dips is a part of time series decomposition result.",
    )
    hasStepChanges: Optional[bool] = Field(
        None,
        description="If true, step_changes is a part of time series decomposition result.",
    )
    nonSeasonalOrder: Optional[ArimaOrder] = Field(
        None, description="Non-seasonal order."
    )
    seasonalPeriods: Optional[List[SeasonalPeriod]] = Field(
        None,
        description="Seasonal periods. Repeated because multiple periods are supported for one time series.",
    )
    timeSeriesId: Optional[str] = Field(
        None,
        description="The time_series_id value for this time series. It will be one of the unique values from the time_series_id_column specified during ARIMA model training. Only present when time_series_id_column training option was used.",
    )
    timeSeriesIds: Optional[List[str]] = Field(
        None,
        description="The tuple of time_series_ids identifying this time series. It will be one of the unique tuples of values present in the time_series_id_columns specified during ARIMA model training. Only present when time_series_id_columns training option was used and the order of values here are same as the order of time_series_id_columns.",
    )


class LogType(Enum):
    LOG_TYPE_UNSPECIFIED = "LOG_TYPE_UNSPECIFIED"
    ADMIN_READ = "ADMIN_READ"
    DATA_WRITE = "DATA_WRITE"
    DATA_READ = "DATA_READ"


class AuditLogConfig(BaseModel):
    exemptedMembers: Optional[List[str]] = Field(
        None,
        description="Specifies the identities that do not cause logging for this type of permission. Follows the same format of Binding.members.",
    )
    logType: Optional[LogType] = Field(
        None, description="The log type that this config enables."
    )


class AvroOptions(BaseModel):
    useAvroLogicalTypes: Optional[bool] = Field(
        None,
        description='Optional. If sourceFormat is set to "AVRO", indicates whether to interpret logical types as the corresponding BigQuery data type (for example, TIMESTAMP), instead of using the raw type (for example, INTEGER).',
    )


class BatchDeleteRowAccessPoliciesRequest(BaseModel):
    force: Optional[bool] = Field(
        None,
        description="If set to true, it deletes the row access policy even if it's the last row access policy on the table and the deletion will widen the access rather narrowing it.",
    )
    policyIds: Optional[List[str]] = Field(
        None, description="Required. Policy IDs of the row access policies."
    )


class Code(Enum):
    CODE_UNSPECIFIED = "CODE_UNSPECIFIED"
    NO_RESERVATION = "NO_RESERVATION"
    INSUFFICIENT_RESERVATION = "INSUFFICIENT_RESERVATION"
    UNSUPPORTED_SQL_TEXT = "UNSUPPORTED_SQL_TEXT"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    OTHER_REASON = "OTHER_REASON"
    TABLE_EXCLUDED = "TABLE_EXCLUDED"


class BiEngineReason(BaseModel):
    code: Optional[Code] = Field(
        None,
        description="Output only. High-level BI Engine reason for partial or disabled acceleration",
    )
    message: Optional[str] = Field(
        None,
        description="Output only. Free form human-readable reason for partial or disabled acceleration.",
    )


class AccelerationMode(Enum):
    BI_ENGINE_ACCELERATION_MODE_UNSPECIFIED = "BI_ENGINE_ACCELERATION_MODE_UNSPECIFIED"
    BI_ENGINE_DISABLED = "BI_ENGINE_DISABLED"
    PARTIAL_INPUT = "PARTIAL_INPUT"
    FULL_INPUT = "FULL_INPUT"
    FULL_QUERY = "FULL_QUERY"


class BiEngineMode(Enum):
    ACCELERATION_MODE_UNSPECIFIED = "ACCELERATION_MODE_UNSPECIFIED"
    DISABLED = "DISABLED"
    PARTIAL = "PARTIAL"
    FULL = "FULL"


class BiEngineStatistics(BaseModel):
    accelerationMode: Optional[AccelerationMode] = Field(
        None,
        description="Output only. Specifies which mode of BI Engine acceleration was performed (if any).",
    )
    biEngineMode: Optional[BiEngineMode] = Field(
        None,
        description="Output only. Specifies which mode of BI Engine acceleration was performed (if any).",
    )
    biEngineReasons: Optional[List[BiEngineReason]] = Field(
        None,
        description="In case of DISABLED or PARTIAL bi_engine_mode, these contain the explanatory reasons as to why BI Engine could not accelerate. In case the full query was accelerated, this field is not populated.",
    )


class FileFormat(Enum):
    FILE_FORMAT_UNSPECIFIED = "FILE_FORMAT_UNSPECIFIED"
    PARQUET = "PARQUET"


class TableFormat(Enum):
    TABLE_FORMAT_UNSPECIFIED = "TABLE_FORMAT_UNSPECIFIED"
    ICEBERG = "ICEBERG"


class BigLakeConfiguration(BaseModel):
    connectionId: Optional[str] = Field(
        None,
        description='Optional. The connection specifying the credentials to be used to read and write to external storage, such as Cloud Storage. The connection_id can have the form `{project}.{location}.{connection_id}` or `projects/{project}/locations/{location}/connections/{connection_id}".',
    )
    fileFormat: Optional[FileFormat] = Field(
        None, description="Optional. The file format the table data is stored in."
    )
    storageUri: Optional[str] = Field(
        None,
        description="Optional. The fully qualified location prefix of the external folder where table data is stored. The '*' wildcard character is not allowed. The URI should be in the format `gs://bucket/path_to_table/`",
    )
    tableFormat: Optional[TableFormat] = Field(
        None,
        description="Optional. The table format the metadata only snapshots are stored in.",
    )


class BigQueryModelTraining(BaseModel):
    currentIteration: Optional[int] = Field(None, description="Deprecated.")
    expectedTotalIterations: Optional[str] = Field(None, description="Deprecated.")


class BigtableColumn(BaseModel):
    encoding: Optional[str] = Field(
        None,
        description="Optional. The encoding of the values when the type is not STRING. Acceptable encoding values are: TEXT - indicates values are alphanumeric text strings. BINARY - indicates values are encoded using HBase Bytes.toBytes family of functions. 'encoding' can also be set at the column family level. However, the setting at this level takes precedence if 'encoding' is set at both levels.",
    )
    fieldName: Optional[str] = Field(
        None,
        description="Optional. If the qualifier is not a valid BigQuery field identifier i.e. does not match a-zA-Z*, a valid identifier must be provided as the column field name and is used as field name in queries.",
    )
    onlyReadLatest: Optional[bool] = Field(
        None,
        description="Optional. If this is set, only the latest version of value in this column are exposed. 'onlyReadLatest' can also be set at the column family level. However, the setting at this level takes precedence if 'onlyReadLatest' is set at both levels.",
    )
    qualifierEncoded: Optional[str] = Field(
        None,
        description="[Required] Qualifier of the column. Columns in the parent column family that has this exact qualifier are exposed as `.` field. If the qualifier is valid UTF-8 string, it can be specified in the qualifier_string field. Otherwise, a base-64 encoded value must be set to qualifier_encoded. The column field name is the same as the column qualifier. However, if the qualifier is not a valid BigQuery field identifier i.e. does not match a-zA-Z*, a valid identifier must be provided as field_name.",
    )
    qualifierString: Optional[str] = Field(None, description="Qualifier string.")
    type: Optional[str] = Field(
        None,
        description="Optional. The type to convert the value in cells of this column. The values are expected to be encoded using HBase Bytes.toBytes function when using the BINARY encoding value. Following BigQuery types are allowed (case-sensitive): * BYTES * STRING * INTEGER * FLOAT * BOOLEAN * JSON Default type is BYTES. 'type' can also be set at the column family level. However, the setting at this level takes precedence if 'type' is set at both levels.",
    )


class BigtableColumnFamily(BaseModel):
    columns: Optional[List[BigtableColumn]] = Field(
        None,
        description="Optional. Lists of columns that should be exposed as individual fields as opposed to a list of (column name, value) pairs. All columns whose qualifier matches a qualifier in this list can be accessed as `.`. Other columns can be accessed as a list through the `.Column` field.",
    )
    encoding: Optional[str] = Field(
        None,
        description="Optional. The encoding of the values when the type is not STRING. Acceptable encoding values are: TEXT - indicates values are alphanumeric text strings. BINARY - indicates values are encoded using HBase Bytes.toBytes family of functions. This can be overridden for a specific column by listing that column in 'columns' and specifying an encoding for it.",
    )
    familyId: Optional[str] = Field(
        None, description="Identifier of the column family."
    )
    onlyReadLatest: Optional[bool] = Field(
        None,
        description="Optional. If this is set only the latest version of value are exposed for all columns in this column family. This can be overridden for a specific column by listing that column in 'columns' and specifying a different setting for that column.",
    )
    type: Optional[str] = Field(
        None,
        description="Optional. The type to convert the value in cells of this column family. The values are expected to be encoded using HBase Bytes.toBytes function when using the BINARY encoding value. Following BigQuery types are allowed (case-sensitive): * BYTES * STRING * INTEGER * FLOAT * BOOLEAN * JSON Default type is BYTES. This can be overridden for a specific column by listing that column in 'columns' and specifying a type for it.",
    )


class BigtableOptions(BaseModel):
    columnFamilies: Optional[List[BigtableColumnFamily]] = Field(
        None,
        description="Optional. List of column families to expose in the table schema along with their types. This list restricts the column families that can be referenced in queries and specifies their value types. You can use this list to do type conversions - see the 'type' field for more details. If you leave this list empty, all column families are present in the table schema and their values are read as BYTES. During a query only the column families referenced in that query are read from Bigtable.",
    )
    ignoreUnspecifiedColumnFamilies: Optional[bool] = Field(
        None,
        description="Optional. If field is true, then the column families that are not specified in columnFamilies list are not exposed in the table schema. Otherwise, they are read with BYTES type values. The default value is false.",
    )
    outputColumnFamiliesAsJson: Optional[bool] = Field(
        None,
        description="Optional. If field is true, then each column family will be read as a single JSON column. Otherwise they are read as a repeated cell structure containing timestamp/value tuples. The default value is false.",
    )
    readRowkeyAsString: Optional[bool] = Field(
        None,
        description="Optional. If field is true, then the rowkey column families will be read and converted to string. Otherwise they are read with BYTES type values and users need to manually cast them with CAST if necessary. The default value is false.",
    )


class BinaryConfusionMatrix(BaseModel):
    accuracy: Optional[float] = Field(
        None, description="The fraction of predictions given the correct label."
    )
    f1Score: Optional[float] = Field(
        None, description="The equally weighted average of recall and precision."
    )
    falseNegatives: Optional[str] = Field(
        None, description="Number of false samples predicted as false."
    )
    falsePositives: Optional[str] = Field(
        None, description="Number of false samples predicted as true."
    )
    positiveClassThreshold: Optional[float] = Field(
        None,
        description="Threshold value used when computing each of the following metric.",
    )
    precision: Optional[float] = Field(
        None,
        description="The fraction of actual positive predictions that had positive actual labels.",
    )
    recall: Optional[float] = Field(
        None,
        description="The fraction of actual positive labels that were given a positive prediction.",
    )
    trueNegatives: Optional[str] = Field(
        None, description="Number of true samples predicted as false."
    )
    truePositives: Optional[str] = Field(
        None, description="Number of true samples predicted as true."
    )


class BqmlIterationResult(BaseModel):
    durationMs: Optional[str] = Field(None, description="Deprecated.")
    evalLoss: Optional[float] = Field(None, description="Deprecated.")
    index: Optional[int] = Field(None, description="Deprecated.")
    learnRate: Optional[float] = Field(None, description="Deprecated.")
    trainingLoss: Optional[float] = Field(None, description="Deprecated.")


class TrainingOptions(BaseModel):
    earlyStop: Optional[bool] = None
    l1Reg: Optional[float] = None
    l2Reg: Optional[float] = None
    learnRate: Optional[float] = None
    learnRateStrategy: Optional[str] = None
    lineSearchInitLearnRate: Optional[float] = None
    maxIteration: Optional[str] = None
    minRelProgress: Optional[float] = None
    warmStart: Optional[bool] = None


class BqmlTrainingRun(BaseModel):
    iterationResults: Optional[List[BqmlIterationResult]] = Field(
        None, description="Deprecated."
    )
    startTime: Optional[AwareDatetime] = Field(None, description="Deprecated.")
    state: Optional[str] = Field(None, description="Deprecated.")
    trainingOptions: Optional[TrainingOptions] = Field(None, description="Deprecated.")


class CategoryCount(BaseModel):
    category: Optional[str] = Field(None, description="The name of category.")
    count: Optional[str] = Field(
        None,
        description="The count of training samples matching the category within the cluster.",
    )


class ClusterInfo(BaseModel):
    centroidId: Optional[str] = Field(None, description="Centroid id.")
    clusterRadius: Optional[float] = Field(
        None,
        description="Cluster radius, the average distance from centroid to each point assigned to the cluster.",
    )
    clusterSize: Optional[str] = Field(
        None,
        description="Cluster size, the total number of points assigned to the cluster.",
    )


class Clustering(BaseModel):
    fields: Optional[List[str]] = Field(
        None,
        description="One or more fields on which data should be clustered. Only top-level, non-repeated, simple-type fields are supported. The ordering of the clustering fields should be prioritized from most to least important for filtering purposes. For additional information, see [Introduction to clustered tables](https://cloud.google.com/bigquery/docs/clustered-tables#limitations).",
    )


class ConnectionProperty(BaseModel):
    key: Optional[str] = Field(None, description="The key of the property to set.")
    value: Optional[str] = Field(None, description="The value of the property to set.")


class CsvOptions(BaseModel):
    allowJaggedRows: Optional[bool] = Field(
        None,
        description="Optional. Indicates if BigQuery should accept rows that are missing trailing optional columns. If true, BigQuery treats missing trailing columns as null values. If false, records with missing trailing columns are treated as bad records, and if there are too many bad records, an invalid error is returned in the job result. The default value is false.",
    )
    allowQuotedNewlines: Optional[bool] = Field(
        None,
        description="Optional. Indicates if BigQuery should allow quoted data sections that contain newline characters in a CSV file. The default value is false.",
    )
    encoding: Optional[str] = Field(
        None,
        description="Optional. The character encoding of the data. The supported values are UTF-8, ISO-8859-1, UTF-16BE, UTF-16LE, UTF-32BE, and UTF-32LE. The default value is UTF-8. BigQuery decodes the data after the raw, binary data has been split using the values of the quote and fieldDelimiter properties.",
    )
    fieldDelimiter: Optional[str] = Field(
        None,
        description='Optional. The separator character for fields in a CSV file. The separator is interpreted as a single byte. For files encoded in ISO-8859-1, any single character can be used as a separator. For files encoded in UTF-8, characters represented in decimal range 1-127 (U+0001-U+007F) can be used without any modification. UTF-8 characters encoded with multiple bytes (i.e. U+0080 and above) will have only the first byte used for separating fields. The remaining bytes will be treated as a part of the field. BigQuery also supports the escape sequence "\\t" (U+0009) to specify a tab separator. The default value is comma (",", U+002C).',
    )
    nullMarker: Optional[str] = Field(
        None,
        description='Optional. Specifies a string that represents a null value in a CSV file. For example, if you specify "\\N", BigQuery interprets "\\N" as a null value when querying a CSV file. The default value is the empty string. If you set this property to a custom value, BigQuery throws an error if an empty string is present for all data types except for STRING and BYTE. For STRING and BYTE columns, BigQuery interprets the empty string as an empty value.',
    )
    nullMarkers: Optional[List[str]] = Field(
        None,
        description="Optional. A list of strings represented as SQL NULL value in a CSV file. null_marker and null_markers can't be set at the same time. If null_marker is set, null_markers has to be not set. If null_markers is set, null_marker has to be not set. If both null_marker and null_markers are set at the same time, a user error would be thrown. Any strings listed in null_markers, including empty string would be interpreted as SQL NULL. This applies to all column types.",
    )
    preserveAsciiControlCharacters: Optional[bool] = Field(
        None,
        description="Optional. Indicates if the embedded ASCII control characters (the first 32 characters in the ASCII-table, from '\\x00' to '\\x1F') are preserved.",
    )
    quote: Optional[constr(pattern=r".?")] = Field(
        '"',
        description="Optional. The value that is used to quote data sections in a CSV file. BigQuery converts the string to ISO-8859-1 encoding, and then uses the first byte of the encoded string to split the data in its raw, binary state. The default value is a double-quote (\"). If your data does not contain quoted sections, set the property value to an empty string. If your data contains quoted newline characters, you must also set the allowQuotedNewlines property to true. To include the specific quote character within a quoted value, precede it with an additional matching quote character. For example, if you want to escape the default character ' \" ', use ' \"\" '.",
    )
    skipLeadingRows: Optional[str] = Field(
        None,
        description="Optional. The number of rows at the top of a CSV file that BigQuery will skip when reading the data. The default value is 0. This property is useful if you have header rows in the file that should be skipped. When autodetect is on, the behavior is the following: * skipLeadingRows unspecified - Autodetect tries to detect headers in the first row. If they are not detected, the row is read as data. Otherwise data is read starting from the second row. * skipLeadingRows is 0 - Instructs autodetect that there are no headers and data should be read starting from the first row. * skipLeadingRows = N > 0 - Autodetect skips N-1 rows and tries to detect headers in row N. If headers are not detected, row N is just skipped. Otherwise row N is used to extract column names for the detected schema.",
    )
    sourceColumnMatch: Optional[str] = Field(
        None,
        description="Optional. Controls the strategy used to match loaded columns to the schema. If not set, a sensible default is chosen based on how the schema is provided. If autodetect is used, then columns are matched by name. Otherwise, columns are matched by position. This is done to keep the behavior backward-compatible. Acceptable values are: POSITION - matches by position. This assumes that the columns are ordered the same way as the schema. NAME - matches by name. This reads the header row as column names and reorders columns to match the field names in the schema.",
    )


class DataFormatOptions(BaseModel):
    useInt64Timestamp: Optional[bool] = Field(
        None, description="Optional. Output timestamp as usec int64. Default is false."
    )


class DataMaskingStatistics(BaseModel):
    dataMaskingApplied: Optional[bool] = Field(
        None, description="Whether any accessed data was protected by the data masking."
    )


class DataPolicyOption(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Data policy resource name in the form of projects/project_id/locations/location_id/dataPolicies/data_policy_id.",
    )


class Tag(BaseModel):
    tagKey: Optional[str] = Field(
        None,
        description='Required. The namespaced friendly name of the tag key, e.g. "12345/environment" where 12345 is org id.',
    )
    tagValue: Optional[str] = Field(
        None,
        description='Required. The friendly short name of the tag value, e.g. "production".',
    )


class DefaultRoundingMode(Enum):
    ROUNDING_MODE_UNSPECIFIED = "ROUNDING_MODE_UNSPECIFIED"
    ROUND_HALF_AWAY_FROM_ZERO = "ROUND_HALF_AWAY_FROM_ZERO"
    ROUND_HALF_EVEN = "ROUND_HALF_EVEN"


class StorageBillingModel(Enum):
    STORAGE_BILLING_MODEL_UNSPECIFIED = "STORAGE_BILLING_MODEL_UNSPECIFIED"
    LOGICAL = "LOGICAL"
    PHYSICAL = "PHYSICAL"


class TargetType(Enum):
    TARGET_TYPE_UNSPECIFIED = "TARGET_TYPE_UNSPECIFIED"
    VIEWS = "VIEWS"
    ROUTINES = "ROUTINES"


class DatasetReference(BaseModel):
    datasetId: Optional[str] = Field(
        None,
        description="Required. A unique ID for this dataset, without the project name. The ID must contain only letters (a-z, A-Z), numbers (0-9), or underscores (_). The maximum length is 1,024 characters.",
    )
    projectId: Optional[str] = Field(
        None, description="Optional. The ID of the project containing this dataset."
    )


class DestinationTableProperties(BaseModel):
    description: Optional[str] = Field(
        None,
        description="Optional. The description for the destination table. This will only be used if the destination table is newly created. If the table already exists and a value different than the current description is provided, the job will fail.",
    )
    expirationTime: Optional[AwareDatetime] = Field(
        None, description="Internal use only."
    )
    friendlyName: Optional[str] = Field(
        None,
        description="Optional. Friendly name for the destination table. If the table already exists, it should be same as the existing friendly name.",
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional. The labels associated with this table. You can use these to organize and group your tables. This will only be used if the destination table is newly created. If the table already exists and labels are different than the current labels are provided, the job will fail.",
    )


class DifferentialPrivacyPolicy(BaseModel):
    deltaBudget: Optional[float] = Field(
        None,
        description="Optional. The total delta budget for all queries against the privacy-protected view. Each subscriber query against this view charges the amount of delta that is pre-defined by the contributor through the privacy policy delta_per_query field. If there is sufficient budget, then the subscriber query attempts to complete. It might still fail due to other reasons, in which case the charge is refunded. If there is insufficient budget the query is rejected. There might be multiple charge attempts if a single query references multiple views. In this case there must be sufficient budget for all charges or the query is rejected and charges are refunded in best effort. The budget does not have a refresh policy and can only be updated via ALTER VIEW or circumvented by creating a new view that can be queried with a fresh budget.",
    )
    deltaBudgetRemaining: Optional[float] = Field(
        None,
        description="Output only. The delta budget remaining. If budget is exhausted, no more queries are allowed. Note that the budget for queries that are in progress is deducted before the query executes. If the query fails or is cancelled then the budget is refunded. In this case the amount of budget remaining can increase.",
    )
    deltaPerQuery: Optional[float] = Field(
        None,
        description="Optional. The delta value that is used per query. Delta represents the probability that any row will fail to be epsilon differentially private. Indicates the risk associated with exposing aggregate rows in the result of a query.",
    )
    epsilonBudget: Optional[float] = Field(
        None,
        description="Optional. The total epsilon budget for all queries against the privacy-protected view. Each subscriber query against this view charges the amount of epsilon they request in their query. If there is sufficient budget, then the subscriber query attempts to complete. It might still fail due to other reasons, in which case the charge is refunded. If there is insufficient budget the query is rejected. There might be multiple charge attempts if a single query references multiple views. In this case there must be sufficient budget for all charges or the query is rejected and charges are refunded in best effort. The budget does not have a refresh policy and can only be updated via ALTER VIEW or circumvented by creating a new view that can be queried with a fresh budget.",
    )
    epsilonBudgetRemaining: Optional[float] = Field(
        None,
        description="Output only. The epsilon budget remaining. If budget is exhausted, no more queries are allowed. Note that the budget for queries that are in progress is deducted before the query executes. If the query fails or is cancelled then the budget is refunded. In this case the amount of budget remaining can increase.",
    )
    maxEpsilonPerQuery: Optional[float] = Field(
        None,
        description="Optional. The maximum epsilon value that a query can consume. If the subscriber specifies epsilon as a parameter in a SELECT query, it must be less than or equal to this value. The epsilon parameter controls the amount of noise that is added to the groups — a higher epsilon means less noise.",
    )
    maxGroupsContributed: Optional[str] = Field(
        None,
        description="Optional. The maximum groups contributed value that is used per query. Represents the maximum number of groups to which each protected entity can contribute. Changing this value does not improve or worsen privacy. The best value for accuracy and utility depends on the query and data.",
    )
    privacyUnitColumn: Optional[str] = Field(
        None,
        description="Optional. The privacy unit column associated with this policy. Differential privacy policies can only have one privacy unit column per data source object (table, view).",
    )


class DimensionalityReductionMetrics(BaseModel):
    totalExplainedVarianceRatio: Optional[float] = Field(
        None,
        description="Total percentage of variance explained by the selected principal components.",
    )


class DmlStatistics(BaseModel):
    deletedRowCount: Optional[str] = Field(
        None,
        description="Output only. Number of deleted Rows. populated by DML DELETE, MERGE and TRUNCATE statements.",
    )
    insertedRowCount: Optional[str] = Field(
        None,
        description="Output only. Number of inserted Rows. Populated by DML INSERT and MERGE statements",
    )
    updatedRowCount: Optional[str] = Field(
        None,
        description="Output only. Number of updated Rows. Populated by DML UPDATE and MERGE statements.",
    )


class DoubleCandidates(BaseModel):
    candidates: Optional[List[float]] = Field(
        None, description="Candidates for the double parameter in increasing order."
    )


class DoubleRange(BaseModel):
    max: Optional[float] = Field(None, description="Max value of the double parameter.")
    min: Optional[float] = Field(None, description="Min value of the double parameter.")


class EncryptionConfiguration(BaseModel):
    kmsKeyName: Optional[str] = Field(
        None,
        description="Optional. Describes the Cloud KMS encryption key that will be used to protect destination BigQuery table. The BigQuery Service Account associated with your project requires access to this encryption key.",
    )


class Entry(BaseModel):
    itemCount: Optional[str] = Field(
        None, description="Number of items being predicted as this label."
    )
    predictedLabel: Optional[str] = Field(
        None,
        description="The predicted label. For confidence_threshold > 0, we will also add an entry indicating the number of items under the confidence threshold.",
    )


class ErrorProto(BaseModel):
    debugInfo: Optional[str] = Field(
        None,
        description="Debugging information. This property is internal to Google and should not be used.",
    )
    location: Optional[str] = Field(
        None, description="Specifies where the error occurred, if present."
    )
    message: Optional[str] = Field(
        None, description="A human-readable description of the error."
    )
    reason: Optional[str] = Field(
        None, description="A short error code that summarizes the error."
    )


class ComputeMode(Enum):
    COMPUTE_MODE_UNSPECIFIED = "COMPUTE_MODE_UNSPECIFIED"
    BIGQUERY = "BIGQUERY"
    BI_ENGINE = "BI_ENGINE"


class ExplainQueryStep(BaseModel):
    kind: Optional[str] = Field(None, description="Machine-readable operation type.")
    substeps: Optional[List[str]] = Field(
        None, description="Human-readable description of the step(s)."
    )


class Explanation(BaseModel):
    attribution: Optional[float] = Field(None, description="Attribution of feature.")
    featureName: Optional[str] = Field(
        None,
        description="The full feature name. For non-numerical features, will be formatted like `.`. Overall size of feature name will always be truncated to first 120 characters.",
    )


class ExportDataStatistics(BaseModel):
    fileCount: Optional[str] = Field(
        None,
        description="Number of destination files generated in case of EXPORT DATA statement only.",
    )
    rowCount: Optional[str] = Field(
        None,
        description="[Alpha] Number of destination rows generated in case of EXPORT DATA statement only.",
    )


class Expr(BaseModel):
    description: Optional[str] = Field(
        None,
        description="Optional. Description of the expression. This is a longer text which describes the expression, e.g. when hovered over it in a UI.",
    )
    expression: Optional[str] = Field(
        None,
        description="Textual representation of an expression in Common Expression Language syntax.",
    )
    location: Optional[str] = Field(
        None,
        description="Optional. String indicating the location of the expression for error reporting, e.g. a file name and a position in the file.",
    )
    title: Optional[str] = Field(
        None,
        description="Optional. Title for the expression, i.e. a short string describing its purpose. This can be used e.g. in UIs which allow to enter the expression.",
    )


class ExternalCatalogDatasetOptions(BaseModel):
    parameters: Optional[Dict[str, str]] = Field(
        None,
        description="Optional. A map of key value pairs defining the parameters and properties of the open source schema. Maximum size of 2MiB.",
    )
    defaultStorageLocationUri: Optional[str] = Field(
        None,
        description="Optional. The storage location URI for all tables in the dataset. Equivalent to hive metastore's database locationUri. Maximum length of 1024 characters.",
    )


class DecimalTargetType(Enum):
    DECIMAL_TARGET_TYPE_UNSPECIFIED = "DECIMAL_TARGET_TYPE_UNSPECIFIED"
    NUMERIC = "NUMERIC"
    BIGNUMERIC = "BIGNUMERIC"
    STRING = "STRING"


class FileSetSpecType(Enum):
    FILE_SET_SPEC_TYPE_FILE_SYSTEM_MATCH = "FILE_SET_SPEC_TYPE_FILE_SYSTEM_MATCH"
    FILE_SET_SPEC_TYPE_NEW_LINE_DELIMITED_MANIFEST = (
        "FILE_SET_SPEC_TYPE_NEW_LINE_DELIMITED_MANIFEST"
    )


class JsonExtension(Enum):
    JSON_EXTENSION_UNSPECIFIED = "JSON_EXTENSION_UNSPECIFIED"
    GEOJSON = "GEOJSON"


class MetadataCacheMode(Enum):
    METADATA_CACHE_MODE_UNSPECIFIED = "METADATA_CACHE_MODE_UNSPECIFIED"
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"


class ObjectMetadata(Enum):
    OBJECT_METADATA_UNSPECIFIED = "OBJECT_METADATA_UNSPECIFIED"
    DIRECTORY = "DIRECTORY"
    SIMPLE = "SIMPLE"


class ExternalDatasetReference(BaseModel):
    connection: Optional[str] = Field(
        None,
        description="Required. The connection id that is used to access the external_source. Format: projects/{project_id}/locations/{location_id}/connections/{connection_id}",
    )
    externalSource: Optional[str] = Field(
        None, description="Required. External source that backs this dataset."
    )


class ExternalServiceCost(BaseModel):
    bytesBilled: Optional[str] = Field(
        None, description="External service cost in terms of bigquery bytes billed."
    )
    bytesProcessed: Optional[str] = Field(
        None, description="External service cost in terms of bigquery bytes processed."
    )
    externalService: Optional[str] = Field(None, description="External service name.")
    reservedSlotCount: Optional[str] = Field(
        None,
        description="Non-preemptable reserved slots used for external job. For example, reserved slots for Cloua AI Platform job are the VM usages converted to BigQuery slot with equivalent mount of price.",
    )
    slotMs: Optional[str] = Field(
        None,
        description="External service cost in terms of bigquery slot milliseconds.",
    )


class TypeSystem(Enum):
    TYPE_SYSTEM_UNSPECIFIED = "TYPE_SYSTEM_UNSPECIFIED"
    HIVE = "HIVE"


class ForeignTypeInfo(BaseModel):
    typeSystem: Optional[TypeSystem] = Field(
        None,
        description="Required. Specifies the system which defines the foreign data type.",
    )


class ForeignViewDefinition(BaseModel):
    dialect: Optional[str] = Field(
        None, description="Optional. Represents the dialect of the query."
    )
    query: Optional[str] = Field(
        None, description="Required. The query that defines the view."
    )


class GetPolicyOptions(BaseModel):
    requestedPolicyVersion: Optional[int] = Field(
        None,
        description="Optional. The maximum policy version that will be used to format the policy. Valid values are 0, 1, and 3. Requests specifying an invalid value will be rejected. Requests for policies with any conditional role bindings must specify version 3. Policies with no conditional role bindings may specify any valid value or leave the field unset. The policy in the response might use the policy version that you specified, or it might use a lower policy version. For example, if you specify version 3, but the policy has no conditional role bindings, the response uses version 1. To learn which resources support conditions in their IAM policies, see the [IAM documentation](https://cloud.google.com/iam/help/conditions/resource-policies).",
    )


class GetServiceAccountResponse(BaseModel):
    email: Optional[str] = Field(None, description="The service account email address.")
    kind: Optional[str] = Field(
        "bigquery#getServiceAccountResponse",
        description="The resource type of the response.",
    )


class GlobalExplanation(BaseModel):
    classLabel: Optional[str] = Field(
        None,
        description="Class label for this set of global explanations. Will be empty/null for binary logistic and linear regression models. Sorted alphabetically in descending order.",
    )
    explanations: Optional[List[Explanation]] = Field(
        None,
        description="A list of the top global explanations. Sorted by absolute value of attribution in descending order.",
    )


class GoogleSheetsOptions(BaseModel):
    range: Optional[str] = Field(
        None,
        description="Optional. Range of a sheet to query from. Only used when non-empty. Typical format: sheet_name!top_left_cell_id:bottom_right_cell_id For example: sheet1!A1:B20",
    )
    skipLeadingRows: Optional[str] = Field(
        None,
        description="Optional. The number of rows at the top of a sheet that BigQuery will skip when reading the data. The default value is 0. This property is useful if you have header rows that should be skipped. When autodetect is on, the behavior is the following: * skipLeadingRows unspecified - Autodetect tries to detect headers in the first row. If they are not detected, the row is read as data. Otherwise data is read starting from the second row. * skipLeadingRows is 0 - Instructs autodetect that there are no headers and data should be read starting from the first row. * skipLeadingRows = N > 0 - Autodetect skips N-1 rows and tries to detect headers in row N. If headers are not detected, row N is just skipped. Otherwise row N is used to extract column names for the detected schema.",
    )


class HighCardinalityJoin(BaseModel):
    leftRows: Optional[str] = Field(
        None, description="Output only. Count of left input rows."
    )
    outputRows: Optional[str] = Field(
        None, description="Output only. Count of the output rows."
    )
    rightRows: Optional[str] = Field(
        None, description="Output only. Count of right input rows."
    )
    stepIndex: Optional[int] = Field(
        None,
        description="Output only. The index of the join operator in the ExplainQueryStep lists.",
    )


class HivePartitioningOptions(BaseModel):
    fields: Optional[List[str]] = Field(
        None,
        description="Output only. For permanent external tables, this field is populated with the hive partition keys in the order they were inferred. The types of the partition keys can be deduced by checking the table schema (which will include the partition keys). Not every API will populate this field in the output. For example, Tables.Get will populate it, but Tables.List will not contain this field.",
    )
    mode: Optional[str] = Field(
        None,
        description="Optional. When set, what mode of hive partitioning to use when reading data. The following modes are supported: * AUTO: automatically infer partition key name(s) and type(s). * STRINGS: automatically infer partition key name(s). All types are strings. * CUSTOM: partition key schema is encoded in the source URI prefix. Not all storage formats support hive partitioning. Requesting hive partitioning on an unsupported format will lead to an error. Currently supported formats are: JSON, CSV, ORC, Avro and Parquet.",
    )
    requirePartitionFilter: Optional[bool] = Field(
        False,
        description="Optional. If set to true, queries over this table require a partition filter that can be used for partition elimination to be specified. Note that this field should only be true when creating a permanent external table or querying a temporary external table. Hive-partitioned loads with require_partition_filter explicitly set to true will fail.",
    )
    sourceUriPrefix: Optional[str] = Field(
        None,
        description="Optional. When hive partition detection is requested, a common prefix for all source uris must be required. The prefix must end immediately before the partition key encoding begins. For example, consider files following this data layout: gs://bucket/path_to_table/dt=2019-06-01/country=USA/id=7/file.avro gs://bucket/path_to_table/dt=2019-05-31/country=CA/id=3/file.avro When hive partitioning is requested with either AUTO or STRINGS detection, the common prefix can be either of gs://bucket/path_to_table or gs://bucket/path_to_table/. CUSTOM detection requires encoding the partitioning schema immediately after the common prefix. For CUSTOM, any of * gs://bucket/path_to_table/{dt:DATE}/{country:STRING}/{id:INTEGER} * gs://bucket/path_to_table/{dt:STRING}/{country:STRING}/{id:INTEGER} * gs://bucket/path_to_table/{dt:DATE}/{country:STRING}/{id:STRING} would all be valid source URI prefixes.",
    )


class Status(Enum):
    TRIAL_STATUS_UNSPECIFIED = "TRIAL_STATUS_UNSPECIFIED"
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INFEASIBLE = "INFEASIBLE"
    STOPPED_EARLY = "STOPPED_EARLY"


class Code1(Enum):
    CODE_UNSPECIFIED = "CODE_UNSPECIFIED"
    INDEX_CONFIG_NOT_AVAILABLE = "INDEX_CONFIG_NOT_AVAILABLE"
    PENDING_INDEX_CREATION = "PENDING_INDEX_CREATION"
    BASE_TABLE_TRUNCATED = "BASE_TABLE_TRUNCATED"
    INDEX_CONFIG_MODIFIED = "INDEX_CONFIG_MODIFIED"
    TIME_TRAVEL_QUERY = "TIME_TRAVEL_QUERY"
    NO_PRUNING_POWER = "NO_PRUNING_POWER"
    UNINDEXED_SEARCH_FIELDS = "UNINDEXED_SEARCH_FIELDS"
    UNSUPPORTED_SEARCH_PATTERN = "UNSUPPORTED_SEARCH_PATTERN"
    OPTIMIZED_WITH_MATERIALIZED_VIEW = "OPTIMIZED_WITH_MATERIALIZED_VIEW"
    SECURED_BY_DATA_MASKING = "SECURED_BY_DATA_MASKING"
    MISMATCHED_TEXT_ANALYZER = "MISMATCHED_TEXT_ANALYZER"
    BASE_TABLE_TOO_SMALL = "BASE_TABLE_TOO_SMALL"
    BASE_TABLE_TOO_LARGE = "BASE_TABLE_TOO_LARGE"
    ESTIMATED_PERFORMANCE_GAIN_TOO_LOW = "ESTIMATED_PERFORMANCE_GAIN_TOO_LOW"
    NOT_SUPPORTED_IN_STANDARD_EDITION = "NOT_SUPPORTED_IN_STANDARD_EDITION"
    INDEX_SUPPRESSED_BY_FUNCTION_OPTION = "INDEX_SUPPRESSED_BY_FUNCTION_OPTION"
    QUERY_CACHE_HIT = "QUERY_CACHE_HIT"
    STALE_INDEX = "STALE_INDEX"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    OTHER_REASON = "OTHER_REASON"


class InputDataChange(BaseModel):
    recordsReadDiffPercentage: Optional[float] = Field(
        None,
        description="Output only. Records read difference percentage compared to a previous run.",
    )


class IntArray(BaseModel):
    elements: Optional[List[str]] = Field(
        None, description="Elements in the int array."
    )


class IntArrayHparamSearchSpace(BaseModel):
    candidates: Optional[List[IntArray]] = Field(
        None, description="Candidates for the int array parameter."
    )


class IntCandidates(BaseModel):
    candidates: Optional[List[str]] = Field(
        None, description="Candidates for the int parameter in increasing order."
    )


class IntRange(BaseModel):
    max: Optional[str] = Field(None, description="Max value of the int parameter.")
    min: Optional[str] = Field(None, description="Min value of the int parameter.")


class ColumnNameCharacterMap(Enum):
    COLUMN_NAME_CHARACTER_MAP_UNSPECIFIED = "COLUMN_NAME_CHARACTER_MAP_UNSPECIFIED"
    STRICT = "STRICT"
    V1 = "V1"
    V2 = "V2"


class SourceColumnMatch(Enum):
    SOURCE_COLUMN_MATCH_UNSPECIFIED = "SOURCE_COLUMN_MATCH_UNSPECIFIED"
    POSITION = "POSITION"
    NAME = "NAME"


class OperationType(Enum):
    OPERATION_TYPE_UNSPECIFIED = "OPERATION_TYPE_UNSPECIFIED"
    COPY = "COPY"
    SNAPSHOT = "SNAPSHOT"
    RESTORE = "RESTORE"
    CLONE = "CLONE"


class Code2(Enum):
    CODE_UNSPECIFIED = "CODE_UNSPECIFIED"
    REQUESTED = "REQUESTED"
    LONG_RUNNING = "LONG_RUNNING"
    LARGE_RESULTS = "LARGE_RESULTS"
    OTHER = "OTHER"


class JobCreationReason(BaseModel):
    code: Optional[Code2] = Field(
        None,
        description="Output only. Specifies the high level reason why a Job was created.",
    )


class JobReference(BaseModel):
    jobId: Optional[str] = Field(
        None,
        description="Required. The ID of the job. The ID must contain only letters (a-z, A-Z), numbers (0-9), underscores (_), or dashes (-). The maximum length is 1,024 characters.",
    )
    location: Optional[str] = Field(
        None,
        description="Optional. The geographic location of the job. The default value is US. For more information about BigQuery locations, see: https://cloud.google.com/bigquery/docs/locations",
    )
    projectId: Optional[str] = Field(
        None, description="Required. The ID of the project containing this job."
    )


class Edition(Enum):
    RESERVATION_EDITION_UNSPECIFIED = "RESERVATION_EDITION_UNSPECIFIED"
    STANDARD = "STANDARD"
    ENTERPRISE = "ENTERPRISE"
    ENTERPRISE_PLUS = "ENTERPRISE_PLUS"


class ReservationUsageItem(BaseModel):
    name: Optional[str] = Field(
        None,
        description='Reservation name or "unreserved" for on-demand resource usage and multi-statement queries.',
    )
    slotMs: Optional[str] = Field(
        None,
        description="Total slot milliseconds used by the reservation for a particular job.",
    )


class JobStatistics5(BaseModel):
    copiedLogicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of logical bytes copied to the destination table.",
    )
    copiedRows: Optional[str] = Field(
        None, description="Output only. Number of rows copied to the destination table."
    )


class JobStatus(BaseModel):
    errorResult: Optional[ErrorProto] = Field(
        None,
        description="Output only. Final error result of the job. If present, indicates that the job has completed and was unsuccessful.",
    )
    errors: Optional[List[ErrorProto]] = Field(
        None,
        description="Output only. The first errors encountered during the running of the job. The final message includes the number of errors that caused the process to stop. Errors here do not necessarily mean that the job has not completed or was unsuccessful.",
    )
    state: Optional[str] = Field(
        None,
        description="Output only. Running state of the job. Valid states include 'PENDING', 'RUNNING', and 'DONE'.",
    )


class JoinCondition(Enum):
    JOIN_CONDITION_UNSPECIFIED = "JOIN_CONDITION_UNSPECIFIED"
    JOIN_ANY = "JOIN_ANY"
    JOIN_ALL = "JOIN_ALL"
    JOIN_NOT_REQUIRED = "JOIN_NOT_REQUIRED"
    JOIN_BLOCKED = "JOIN_BLOCKED"


class JoinRestrictionPolicy(BaseModel):
    joinAllowedColumns: Optional[List[str]] = Field(
        None,
        description="Optional. The only columns that joins are allowed on. This field is must be specified for join_conditions JOIN_ANY and JOIN_ALL and it cannot be set for JOIN_BLOCKED.",
    )
    joinCondition: Optional[JoinCondition] = Field(
        None,
        description="Optional. Specifies if a join is required or not on queries for the view. Default is JOIN_CONDITION_UNSPECIFIED.",
    )


class JsonOptions(BaseModel):
    encoding: Optional[str] = Field(
        None,
        description="Optional. The character encoding of the data. The supported values are UTF-8, UTF-16BE, UTF-16LE, UTF-32BE, and UTF-32LE. The default value is UTF-8.",
    )


class JsonValue(RootModel[Any]):
    root: Any


class LinkState(Enum):
    LINK_STATE_UNSPECIFIED = "LINK_STATE_UNSPECIFIED"
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"


class LinkedDatasetMetadata(BaseModel):
    linkState: Optional[LinkState] = Field(
        None,
        description="Output only. Specifies whether Linked Dataset is currently in a linked state or not.",
    )


class LinkedDatasetSource(BaseModel):
    sourceDataset: Optional[DatasetReference] = Field(
        None,
        description="The source dataset reference contains project numbers and not project ids.",
    )


class LoadQueryStatistics(BaseModel):
    badRecords: Optional[str] = Field(
        None,
        description="Output only. The number of bad records encountered while processing a LOAD query. Note that if the job has failed because of more bad records encountered than the maximum allowed in the load job configuration, then this number can be less than the total number of bad records present in the input data.",
    )
    bytesTransferred: Optional[str] = Field(
        None,
        description="Output only. This field is deprecated. The number of bytes of source data copied over the network for a `LOAD` query. `transferred_bytes` has the canonical value for physical transferred bytes, which is used for BigQuery Omni billing.",
    )
    inputFileBytes: Optional[str] = Field(
        None, description="Output only. Number of bytes of source data in a LOAD query."
    )
    inputFiles: Optional[str] = Field(
        None, description="Output only. Number of source files in a LOAD query."
    )
    outputBytes: Optional[str] = Field(
        None,
        description="Output only. Size of the loaded data in bytes. Note that while a LOAD query is in the running state, this value may change.",
    )
    outputRows: Optional[str] = Field(
        None,
        description="Output only. Number of rows imported in a LOAD query. Note that while a LOAD query is in the running state, this value may change.",
    )


class LocationMetadata(BaseModel):
    legacyLocationId: Optional[str] = Field(
        None,
        description="The legacy BigQuery location ID, e.g. “EU” for the “europe” location. This is for any API consumers that need the legacy “US” and “EU” locations.",
    )


class RejectedReason(Enum):
    REJECTED_REASON_UNSPECIFIED = "REJECTED_REASON_UNSPECIFIED"
    NO_DATA = "NO_DATA"
    COST = "COST"
    BASE_TABLE_TRUNCATED = "BASE_TABLE_TRUNCATED"
    BASE_TABLE_DATA_CHANGE = "BASE_TABLE_DATA_CHANGE"
    BASE_TABLE_PARTITION_EXPIRATION_CHANGE = "BASE_TABLE_PARTITION_EXPIRATION_CHANGE"
    BASE_TABLE_EXPIRED_PARTITION = "BASE_TABLE_EXPIRED_PARTITION"
    BASE_TABLE_INCOMPATIBLE_METADATA_CHANGE = "BASE_TABLE_INCOMPATIBLE_METADATA_CHANGE"
    TIME_ZONE = "TIME_ZONE"
    OUT_OF_TIME_TRAVEL_WINDOW = "OUT_OF_TIME_TRAVEL_WINDOW"
    BASE_TABLE_FINE_GRAINED_SECURITY_POLICY = "BASE_TABLE_FINE_GRAINED_SECURITY_POLICY"
    BASE_TABLE_TOO_STALE = "BASE_TABLE_TOO_STALE"


class MaterializedViewDefinition(BaseModel):
    allowNonIncrementalDefinition: Optional[bool] = Field(
        None,
        description="Optional. This option declares the intention to construct a materialized view that isn't refreshed incrementally. Non-incremental materialized views support an expanded range of SQL queries. The `allow_non_incremental_definition` option can't be changed after the materialized view is created.",
    )
    enableRefresh: Optional[bool] = Field(
        None,
        description='Optional. Enable automatic refresh of the materialized view when the base table is updated. The default value is "true".',
    )
    lastRefreshTime: Optional[str] = Field(
        None,
        description="Output only. The time when this materialized view was last refreshed, in milliseconds since the epoch.",
    )
    maxStaleness: Optional[str] = Field(
        None,
        description="[Optional] Max staleness of data that could be returned when materizlized view is queried (formatted as Google SQL Interval type).",
    )
    query: Optional[str] = Field(
        None, description="Required. A query whose results are persisted."
    )
    refreshIntervalMs: Optional[str] = Field(
        None,
        description='Optional. The maximum frequency at which this materialized view will be refreshed. The default value is "1800000" (30 minutes).',
    )


class MaterializedViewStatus(BaseModel):
    lastRefreshStatus: Optional[ErrorProto] = Field(
        None,
        description="Output only. Error result of the last automatic refresh. If present, indicates that the last automatic refresh was unsuccessful.",
    )
    refreshWatermark: Optional[str] = Field(
        None,
        description="Output only. Refresh watermark of materialized view. The base tables' data were collected into the materialized view cache until this time.",
    )


class ModelType(Enum):
    MODEL_TYPE_UNSPECIFIED = "MODEL_TYPE_UNSPECIFIED"
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"
    KMEANS = "KMEANS"
    MATRIX_FACTORIZATION = "MATRIX_FACTORIZATION"
    DNN_CLASSIFIER = "DNN_CLASSIFIER"
    TENSORFLOW = "TENSORFLOW"
    DNN_REGRESSOR = "DNN_REGRESSOR"
    XGBOOST = "XGBOOST"
    BOOSTED_TREE_REGRESSOR = "BOOSTED_TREE_REGRESSOR"
    BOOSTED_TREE_CLASSIFIER = "BOOSTED_TREE_CLASSIFIER"
    ARIMA = "ARIMA"
    AUTOML_REGRESSOR = "AUTOML_REGRESSOR"
    AUTOML_CLASSIFIER = "AUTOML_CLASSIFIER"
    PCA = "PCA"
    DNN_LINEAR_COMBINED_CLASSIFIER = "DNN_LINEAR_COMBINED_CLASSIFIER"
    DNN_LINEAR_COMBINED_REGRESSOR = "DNN_LINEAR_COMBINED_REGRESSOR"
    AUTOENCODER = "AUTOENCODER"
    ARIMA_PLUS = "ARIMA_PLUS"
    ARIMA_PLUS_XREG = "ARIMA_PLUS_XREG"
    RANDOM_FOREST_REGRESSOR = "RANDOM_FOREST_REGRESSOR"
    RANDOM_FOREST_CLASSIFIER = "RANDOM_FOREST_CLASSIFIER"
    TENSORFLOW_LITE = "TENSORFLOW_LITE"
    ONNX = "ONNX"
    TRANSFORM_ONLY = "TRANSFORM_ONLY"
    CONTRIBUTION_ANALYSIS = "CONTRIBUTION_ANALYSIS"


class TrainingType(Enum):
    TRAINING_TYPE_UNSPECIFIED = "TRAINING_TYPE_UNSPECIFIED"
    SINGLE_TRAINING = "SINGLE_TRAINING"
    HPARAM_TUNING = "HPARAM_TUNING"


class ModelOptions(BaseModel):
    labels: Optional[List[str]] = None
    lossType: Optional[str] = None
    modelType: Optional[str] = None


class ModelDefinition(BaseModel):
    modelOptions: Optional[ModelOptions] = Field(None, description="Deprecated.")
    trainingRuns: Optional[List[BqmlTrainingRun]] = Field(
        None, description="Deprecated."
    )


class ModelExtractOptions(BaseModel):
    trialId: Optional[str] = Field(
        None,
        description="The 1-based ID of the trial to be exported from a hyperparameter tuning model. If not specified, the trial with id = [Model](https://cloud.google.com/bigquery/docs/reference/rest/v2/models#resource:-model).defaultTrialId is exported. This field is ignored for models not trained with hyperparameter tuning.",
    )


class ModelReference(BaseModel):
    datasetId: Optional[str] = Field(
        None, description="Required. The ID of the dataset containing this model."
    )
    modelId: Optional[str] = Field(
        None,
        description="Required. The ID of the model. The ID must contain only letters (a-z, A-Z), numbers (0-9), or underscores (_). The maximum length is 1,024 characters.",
    )
    projectId: Optional[str] = Field(
        None, description="Required. The ID of the project containing this model."
    )


class MapTargetType(Enum):
    MAP_TARGET_TYPE_UNSPECIFIED = "MAP_TARGET_TYPE_UNSPECIFIED"
    ARRAY_OF_STRUCT = "ARRAY_OF_STRUCT"


class ParquetOptions(BaseModel):
    enableListInference: Optional[bool] = Field(
        None,
        description="Optional. Indicates whether to use schema inference specifically for Parquet LIST logical type.",
    )
    enumAsString: Optional[bool] = Field(
        None,
        description="Optional. Indicates whether to infer Parquet ENUM logical type as STRING instead of BYTES by default.",
    )
    mapTargetType: Optional[MapTargetType] = Field(
        None,
        description="Optional. Indicates how to represent a Parquet map if present.",
    )


class PartitionedColumn(BaseModel):
    field: Optional[str] = Field(
        None, description="Required. The name of the partition column."
    )


class PartitioningDefinition(BaseModel):
    partitionedColumn: Optional[List[PartitionedColumn]] = Field(
        None,
        description="Optional. Details about each partitioning column. This field is output only for all partitioning types other than metastore partitioned tables. BigQuery native tables only support 1 partitioning column. Other table types may support 0, 1 or more partitioning columns. For metastore partitioned tables, the order must match the definition order in the Hive Metastore, where it must match the physical layout of the table. For example, CREATE TABLE a_table(id BIGINT, name STRING) PARTITIONED BY (city STRING, state STRING). In this case the values must be ['city', 'state'] in that order.",
    )


class PrincipalComponentInfo(BaseModel):
    cumulativeExplainedVarianceRatio: Optional[float] = Field(
        None,
        description="The explained_variance is pre-ordered in the descending order to compute the cumulative explained variance ratio.",
    )
    explainedVariance: Optional[float] = Field(
        None,
        description="Explained variance by this principal component, which is simply the eigenvalue.",
    )
    explainedVarianceRatio: Optional[float] = Field(
        None, description="Explained_variance over the total explained variance."
    )
    principalComponentId: Optional[str] = Field(
        None, description="Id of the principal component."
    )


class PrivacyPolicy(BaseModel):
    aggregationThresholdPolicy: Optional[AggregationThresholdPolicy] = Field(
        None, description="Optional. Policy used for aggregation thresholds."
    )
    differentialPrivacyPolicy: Optional[DifferentialPrivacyPolicy] = Field(
        None, description="Optional. Policy used for differential privacy."
    )
    joinRestrictionPolicy: Optional[JoinRestrictionPolicy] = Field(
        None,
        description="Optional. Join restriction policy is outside of the one of policies, since this policy can be set along with other policies. This policy gives data providers the ability to enforce joins on the 'join_allowed_columns' when data is queried from a privacy protected view.",
    )


class ProjectReference(BaseModel):
    projectId: Optional[str] = Field(
        None,
        description="Required. ID of the project. Can be either the numeric ID or the assigned ID of the project.",
    )


class QueryInfo(BaseModel):
    optimizationDetails: Optional[Dict[str, Any]] = Field(
        None, description="Output only. Information about query optimizations."
    )


class JobCreationMode(Enum):
    JOB_CREATION_MODE_UNSPECIFIED = "JOB_CREATION_MODE_UNSPECIFIED"
    JOB_CREATION_REQUIRED = "JOB_CREATION_REQUIRED"
    JOB_CREATION_OPTIONAL = "JOB_CREATION_OPTIONAL"


class QueryTimelineSample(BaseModel):
    activeUnits: Optional[str] = Field(
        None,
        description="Total number of active workers. This does not correspond directly to slot usage. This is the largest value observed since the last sample.",
    )
    completedUnits: Optional[str] = Field(
        None, description="Total parallel units of work completed by this query."
    )
    elapsedMs: Optional[str] = Field(
        None, description="Milliseconds elapsed since the start of query execution."
    )
    estimatedRunnableUnits: Optional[str] = Field(
        None,
        description="Units of work that can be scheduled immediately. Providing additional slots for these units of work will accelerate the query, if no other query in the reservation needs additional slots.",
    )
    pendingUnits: Optional[str] = Field(
        None,
        description="Total units of work remaining for the query. This number can be revised (increased or decreased) while the query is running.",
    )
    totalSlotMs: Optional[str] = Field(
        None, description="Cumulative slot-ms consumed by the query."
    )


class Range(BaseModel):
    end: Optional[str] = Field(
        None, description="[Experimental] The end of range partitioning, exclusive."
    )
    interval: Optional[str] = Field(
        None, description="[Experimental] The width of each interval."
    )
    start: Optional[str] = Field(
        None, description="[Experimental] The start of range partitioning, inclusive."
    )


class RangePartitioning(BaseModel):
    field: Optional[str] = Field(
        None,
        description="Required. The name of the column to partition the table on. It must be a top-level, INT64 column whose mode is NULLABLE or REQUIRED.",
    )
    range: Optional[Range] = Field(
        None, description="[Experimental] Defines the ranges for range partitioning."
    )


class RankingMetrics(BaseModel):
    averageRank: Optional[float] = Field(
        None,
        description="Determines the goodness of a ranking by computing the percentile rank from the predicted confidence and dividing it by the original rank.",
    )
    meanAveragePrecision: Optional[float] = Field(
        None,
        description="Calculates a precision per user for all the items by ranking them and then averages all the precisions across all the users.",
    )
    meanSquaredError: Optional[float] = Field(
        None,
        description="Similar to the mean squared error computed in regression and explicit recommendation models except instead of computing the rating directly, the output from evaluate is computed against a preference which is 1 or 0 depending on if the rating exists or not.",
    )
    normalizedDiscountedCumulativeGain: Optional[float] = Field(
        None,
        description="A metric to determine the goodness of a ranking calculated from the predicted confidence by comparing it to an ideal rank measured by the original ratings.",
    )


class RegressionMetrics(BaseModel):
    meanAbsoluteError: Optional[float] = Field(None, description="Mean absolute error.")
    meanSquaredError: Optional[float] = Field(None, description="Mean squared error.")
    meanSquaredLogError: Optional[float] = Field(
        None, description="Mean squared log error."
    )
    medianAbsoluteError: Optional[float] = Field(
        None, description="Median absolute error."
    )
    rSquared: Optional[float] = Field(
        None, description="R^2 score. This corresponds to r2_score in ML.EVALUATE."
    )


class RemoteFunctionOptions(BaseModel):
    connection: Optional[str] = Field(
        None,
        description='Fully qualified name of the user-provided connection object which holds the authentication information to send requests to the remote service. Format: ```"projects/{projectId}/locations/{locationId}/connections/{connectionId}"```',
    )
    endpoint: Optional[str] = Field(
        None,
        description="Endpoint of the user-provided remote service, e.g. ```https://us-east1-my_gcf_project.cloudfunctions.net/remote_add```",
    )
    maxBatchingRows: Optional[str] = Field(
        None,
        description="Max number of rows in each batch sent to the remote service. If absent or if 0, BigQuery dynamically decides the number of rows in a batch.",
    )
    userDefinedContext: Optional[Dict[str, str]] = Field(
        None,
        description="User-defined context as a set of key/value pairs, which will be sent as function invocation context together with batched arguments in the requests to the remote service. The total number of bytes of keys and values must be less than 8KB.",
    )


class RemoteServiceType(Enum):
    REMOTE_SERVICE_TYPE_UNSPECIFIED = "REMOTE_SERVICE_TYPE_UNSPECIFIED"
    CLOUD_AI_TRANSLATE_V3 = "CLOUD_AI_TRANSLATE_V3"
    CLOUD_AI_VISION_V1 = "CLOUD_AI_VISION_V1"
    CLOUD_AI_NATURAL_LANGUAGE_V1 = "CLOUD_AI_NATURAL_LANGUAGE_V1"
    CLOUD_AI_SPEECH_TO_TEXT_V2 = "CLOUD_AI_SPEECH_TO_TEXT_V2"


class RemoteModelInfo(BaseModel):
    connection: Optional[str] = Field(
        None,
        description='Output only. Fully qualified name of the user-provided connection object of the remote model. Format: ```"projects/{project_id}/locations/{location_id}/connections/{connection_id}"```',
    )
    endpoint: Optional[str] = Field(
        None, description="Output only. The endpoint for remote model."
    )
    maxBatchingRows: Optional[str] = Field(
        None,
        description="Output only. Max number of rows in each batch sent to the remote service. If unset, the number of rows in each batch is set dynamically.",
    )
    remoteModelVersion: Optional[str] = Field(
        None, description="Output only. The model version for LLM."
    )
    remoteServiceType: Optional[RemoteServiceType] = Field(
        None, description="Output only. The remote service type for remote model."
    )
    speechRecognizer: Optional[str] = Field(
        None,
        description="Output only. The name of the speech recognizer to use for speech recognition. The expected format is `projects/{project}/locations/{location}/recognizers/{recognizer}`. Customers can specify this field at model creation. If not specified, a default recognizer `projects/{model project}/locations/global/recognizers/_` will be used. See more details at [recognizers](https://cloud.google.com/speech-to-text/v2/docs/reference/rest/v2/projects.locations.recognizers)",
    )


class Type(Enum):
    RESTRICTION_TYPE_UNSPECIFIED = "RESTRICTION_TYPE_UNSPECIFIED"
    RESTRICTED_DATA_EGRESS = "RESTRICTED_DATA_EGRESS"


class RestrictionConfig(BaseModel):
    type: Optional[Type] = Field(
        None,
        description="Output only. Specifies the type of dataset/table restriction.",
    )


class DataGovernanceType(Enum):
    DATA_GOVERNANCE_TYPE_UNSPECIFIED = "DATA_GOVERNANCE_TYPE_UNSPECIFIED"
    DATA_MASKING = "DATA_MASKING"


class DeterminismLevel(Enum):
    DETERMINISM_LEVEL_UNSPECIFIED = "DETERMINISM_LEVEL_UNSPECIFIED"
    DETERMINISTIC = "DETERMINISTIC"
    NOT_DETERMINISTIC = "NOT_DETERMINISTIC"


class Language(Enum):
    LANGUAGE_UNSPECIFIED = "LANGUAGE_UNSPECIFIED"
    SQL = "SQL"
    JAVASCRIPT = "JAVASCRIPT"
    PYTHON = "PYTHON"
    JAVA = "JAVA"
    SCALA = "SCALA"


class RoutineType(Enum):
    ROUTINE_TYPE_UNSPECIFIED = "ROUTINE_TYPE_UNSPECIFIED"
    SCALAR_FUNCTION = "SCALAR_FUNCTION"
    PROCEDURE = "PROCEDURE"
    TABLE_VALUED_FUNCTION = "TABLE_VALUED_FUNCTION"
    AGGREGATE_FUNCTION = "AGGREGATE_FUNCTION"


class SecurityMode(Enum):
    SECURITY_MODE_UNSPECIFIED = "SECURITY_MODE_UNSPECIFIED"
    DEFINER = "DEFINER"
    INVOKER = "INVOKER"


class RoutineReference(BaseModel):
    datasetId: Optional[str] = Field(
        None, description="Required. The ID of the dataset containing this routine."
    )
    projectId: Optional[str] = Field(
        None, description="Required. The ID of the project containing this routine."
    )
    routineId: Optional[str] = Field(
        None,
        description="Required. The ID of the routine. The ID must contain only letters (a-z, A-Z), numbers (0-9), or underscores (_). The maximum length is 256 characters.",
    )


class Row(BaseModel):
    actualLabel: Optional[str] = Field(
        None, description="The original label of this row."
    )
    entries: Optional[List[Entry]] = Field(
        None, description="Info describing predicted label distribution."
    )


class RowAccessPolicyReference(BaseModel):
    datasetId: Optional[str] = Field(
        None,
        description="Required. The ID of the dataset containing this row access policy.",
    )
    policyId: Optional[str] = Field(
        None,
        description="Required. The ID of the row access policy. The ID must contain only letters (a-z, A-Z), numbers (0-9), or underscores (_). The maximum length is 256 characters.",
    )
    projectId: Optional[str] = Field(
        None,
        description="Required. The ID of the project containing this row access policy.",
    )
    tableId: Optional[str] = Field(
        None,
        description="Required. The ID of the table containing this row access policy.",
    )


class RowLevelSecurityStatistics(BaseModel):
    rowLevelSecurityApplied: Optional[bool] = Field(
        None,
        description="Whether any accessed data was protected by row access policies.",
    )


class KeyResultStatement(Enum):
    KEY_RESULT_STATEMENT_KIND_UNSPECIFIED = "KEY_RESULT_STATEMENT_KIND_UNSPECIFIED"
    LAST = "LAST"
    FIRST_SELECT = "FIRST_SELECT"


class ScriptOptions(BaseModel):
    keyResultStatement: Optional[KeyResultStatement] = Field(
        None,
        description='Determines which statement in the script represents the "key result", used to populate the schema and query results of the script job. Default is LAST.',
    )
    statementByteBudget: Optional[str] = Field(
        None,
        description="Limit on the number of bytes billed per statement. Exceeding this budget results in an error.",
    )
    statementTimeoutMs: Optional[str] = Field(
        None, description="Timeout period for each statement in a script."
    )


class ScriptStackFrame(BaseModel):
    endColumn: Optional[int] = Field(
        None, description="Output only. One-based end column."
    )
    endLine: Optional[int] = Field(None, description="Output only. One-based end line.")
    procedureId: Optional[str] = Field(
        None,
        description="Output only. Name of the active procedure, empty if in a top-level script.",
    )
    startColumn: Optional[int] = Field(
        None, description="Output only. One-based start column."
    )
    startLine: Optional[int] = Field(
        None, description="Output only. One-based start line."
    )
    text: Optional[str] = Field(
        None, description="Output only. Text of the current statement/expression."
    )


class EvaluationKind(Enum):
    EVALUATION_KIND_UNSPECIFIED = "EVALUATION_KIND_UNSPECIFIED"
    STATEMENT = "STATEMENT"
    EXPRESSION = "EXPRESSION"


class ScriptStatistics(BaseModel):
    evaluationKind: Optional[EvaluationKind] = Field(
        None, description="Whether this child job was a statement or expression."
    )
    stackFrames: Optional[List[ScriptStackFrame]] = Field(
        None,
        description="Stack trace showing the line/column/procedure name of each frame on the stack at the point where the current evaluation happened. The leaf frame is first, the primary script is last. Never empty.",
    )


class IndexUsageMode(Enum):
    INDEX_USAGE_MODE_UNSPECIFIED = "INDEX_USAGE_MODE_UNSPECIFIED"
    UNUSED = "UNUSED"
    PARTIALLY_USED = "PARTIALLY_USED"
    FULLY_USED = "FULLY_USED"


class SerDeInfo(BaseModel):
    parameters: Optional[Dict[str, str]] = Field(
        None,
        description="Optional. Key-value pairs that define the initialization parameters for the serialization library. Maximum size 10 Kib.",
    )
    name: Optional[str] = Field(
        None,
        description="Optional. Name of the SerDe. The maximum length is 256 characters.",
    )
    serializationLibrary: Optional[str] = Field(
        None,
        description="Required. Specifies a fully-qualified class name of the serialization library that is responsible for the translation of data between table representation and the underlying low-level input and output format structures. The maximum length is 256 characters.",
    )


class SessionInfo(BaseModel):
    sessionId: Optional[str] = Field(
        None, description="Output only. The id of the session."
    )


class SkewSource(BaseModel):
    stageId: Optional[str] = Field(
        None, description="Output only. Stage id of the skew source stage."
    )


class SparkLoggingInfo(BaseModel):
    projectId: Optional[str] = Field(
        None, description="Output only. Project ID where the Spark logs were written."
    )
    resourceType: Optional[str] = Field(
        None, description="Output only. Resource type used for logging."
    )


class SparkOptions(BaseModel):
    archiveUris: Optional[List[str]] = Field(
        None,
        description="Archive files to be extracted into the working directory of each executor. For more information about Apache Spark, see [Apache Spark](https://spark.apache.org/docs/latest/index.html).",
    )
    connection: Optional[str] = Field(
        None,
        description='Fully qualified name of the user-provided Spark connection object. Format: ```"projects/{project_id}/locations/{location_id}/connections/{connection_id}"```',
    )
    containerImage: Optional[str] = Field(
        None, description="Custom container image for the runtime environment."
    )
    fileUris: Optional[List[str]] = Field(
        None,
        description="Files to be placed in the working directory of each executor. For more information about Apache Spark, see [Apache Spark](https://spark.apache.org/docs/latest/index.html).",
    )
    jarUris: Optional[List[str]] = Field(
        None,
        description="JARs to include on the driver and executor CLASSPATH. For more information about Apache Spark, see [Apache Spark](https://spark.apache.org/docs/latest/index.html).",
    )
    mainClass: Optional[str] = Field(
        None,
        description="The fully qualified name of a class in jar_uris, for example, com.example.wordcount. Exactly one of main_class and main_jar_uri field should be set for Java/Scala language type.",
    )
    mainFileUri: Optional[str] = Field(
        None,
        description="The main file/jar URI of the Spark application. Exactly one of the definition_body field and the main_file_uri field must be set for Python. Exactly one of main_class and main_file_uri field should be set for Java/Scala language type.",
    )
    properties: Optional[Dict[str, str]] = Field(
        None,
        description="Configuration properties as a set of key/value pairs, which will be passed on to the Spark application. For more information, see [Apache Spark](https://spark.apache.org/docs/latest/index.html) and the [procedure option list](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#procedure_option_list).",
    )
    pyFileUris: Optional[List[str]] = Field(
        None,
        description="Python files to be placed on the PYTHONPATH for PySpark application. Supported file types: `.py`, `.egg`, and `.zip`. For more information about Apache Spark, see [Apache Spark](https://spark.apache.org/docs/latest/index.html).",
    )
    runtimeVersion: Optional[str] = Field(
        None,
        description="Runtime version. If not specified, the default runtime version is used.",
    )


class SparkStatistics(BaseModel):
    endpoints: Optional[Dict[str, str]] = Field(
        None,
        description="Output only. Endpoints returned from Dataproc. Key list: - history_server_endpoint: A link to Spark job UI.",
    )
    gcsStagingBucket: Optional[str] = Field(
        None,
        description="Output only. The Google Cloud Storage bucket that is used as the default file system by the Spark application. This field is only filled when the Spark procedure uses the invoker security mode. The `gcsStagingBucket` bucket is inferred from the `@@spark_proc_properties.staging_bucket` system variable (if it is provided). Otherwise, BigQuery creates a default staging bucket for the job and returns the bucket name in this field. Example: * `gs://[bucket_name]`",
    )
    kmsKeyName: Optional[str] = Field(
        None,
        description="Output only. The Cloud KMS encryption key that is used to protect the resources created by the Spark job. If the Spark procedure uses the invoker security mode, the Cloud KMS encryption key is either inferred from the provided system variable, `@@spark_proc_properties.kms_key_name`, or the default key of the BigQuery job's project (if the CMEK organization policy is enforced). Otherwise, the Cloud KMS key is either inferred from the Spark connection associated with the procedure (if it is provided), or from the default key of the Spark connection's project if the CMEK organization policy is enforced. Example: * `projects/[kms_project_id]/locations/[region]/keyRings/[key_region]/cryptoKeys/[key]`",
    )
    loggingInfo: Optional[SparkLoggingInfo] = Field(
        None,
        description="Output only. Logging info is used to generate a link to Cloud Logging.",
    )
    sparkJobId: Optional[str] = Field(
        None,
        description="Output only. Spark job ID if a Spark job is created successfully.",
    )
    sparkJobLocation: Optional[str] = Field(
        None,
        description="Output only. Location where the Spark job is executed. A location is selected by BigQueury for jobs configured to run in a multi-region.",
    )


class StagePerformanceChangeInsight(BaseModel):
    inputDataChange: Optional[InputDataChange] = Field(
        None, description="Output only. Input data change insight of the query stage."
    )
    stageId: Optional[str] = Field(
        None, description="Output only. The stage id that the insight mapped to."
    )


class TypeKind(Enum):
    TYPE_KIND_UNSPECIFIED = "TYPE_KIND_UNSPECIFIED"
    INT64 = "INT64"
    BOOL = "BOOL"
    FLOAT64 = "FLOAT64"
    STRING = "STRING"
    BYTES = "BYTES"
    TIMESTAMP = "TIMESTAMP"
    DATE = "DATE"
    TIME = "TIME"
    DATETIME = "DATETIME"
    INTERVAL = "INTERVAL"
    GEOGRAPHY = "GEOGRAPHY"
    NUMERIC = "NUMERIC"
    BIGNUMERIC = "BIGNUMERIC"
    JSON = "JSON"
    ARRAY = "ARRAY"
    STRUCT = "STRUCT"
    RANGE = "RANGE"


class StorageDescriptor(BaseModel):
    inputFormat: Optional[str] = Field(
        None,
        description='Optional. Specifies the fully qualified class name of the InputFormat (e.g. "org.apache.hadoop.hive.ql.io.orc.OrcInputFormat"). The maximum length is 128 characters.',
    )
    locationUri: Optional[str] = Field(
        None,
        description="Optional. The physical location of the table (e.g. `gs://spark-dataproc-data/pangea-data/case_sensitive/` or `gs://spark-dataproc-data/pangea-data/*`). The maximum length is 2056 bytes.",
    )
    outputFormat: Optional[str] = Field(
        None,
        description='Optional. Specifies the fully qualified class name of the OutputFormat (e.g. "org.apache.hadoop.hive.ql.io.orc.OrcOutputFormat"). The maximum length is 128 characters.',
    )
    serdeInfo: Optional[SerDeInfo] = Field(
        None, description="Optional. Serializer and deserializer information."
    )


class Code3(Enum):
    CODE_UNSPECIFIED = "CODE_UNSPECIFIED"
    STORED_COLUMNS_COVER_INSUFFICIENT = "STORED_COLUMNS_COVER_INSUFFICIENT"
    BASE_TABLE_HAS_RLS = "BASE_TABLE_HAS_RLS"
    BASE_TABLE_HAS_CLS = "BASE_TABLE_HAS_CLS"
    UNSUPPORTED_PREFILTER = "UNSUPPORTED_PREFILTER"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    OTHER_REASON = "OTHER_REASON"


class StoredColumnsUnusedReason(BaseModel):
    code: Optional[Code3] = Field(
        None,
        description="Specifies the high-level reason for the unused scenario, each reason must have a code associated.",
    )
    message: Optional[str] = Field(
        None, description="Specifies the detailed description for the scenario."
    )
    uncoveredColumns: Optional[List[str]] = Field(
        None,
        description="Specifies which columns were not covered by the stored columns for the specified code up to 20 columns. This is populated when the code is STORED_COLUMNS_COVER_INSUFFICIENT and BASE_TABLE_HAS_CLS.",
    )


class Streamingbuffer(BaseModel):
    estimatedBytes: Optional[str] = Field(
        None,
        description="Output only. A lower-bound estimate of the number of bytes currently in the streaming buffer.",
    )
    estimatedRows: Optional[str] = Field(
        None,
        description="Output only. A lower-bound estimate of the number of rows currently in the streaming buffer.",
    )
    oldestEntryTime: Optional[str] = Field(
        None,
        description="Output only. Contains the timestamp of the oldest entry in the streaming buffer, in milliseconds since the epoch, if the streaming buffer is available.",
    )


class StringHparamSearchSpace(BaseModel):
    candidates: Optional[List[str]] = Field(
        None, description="Canididates for the string or enum parameter in lower case."
    )


class ManagedTableType(Enum):
    MANAGED_TABLE_TYPE_UNSPECIFIED = "MANAGED_TABLE_TYPE_UNSPECIFIED"
    NATIVE = "NATIVE"
    ICEBERG = "ICEBERG"


class TableCell(BaseModel):
    v: Optional[Any] = None


class ColumnReference(BaseModel):
    referencedColumn: Optional[str] = Field(
        None,
        description="Required. The column in the primary key that are referenced by the referencing_column.",
    )
    referencingColumn: Optional[str] = Field(
        None, description="Required. The column that composes the foreign key."
    )


class ReferencedTable(BaseModel):
    datasetId: Optional[str] = None
    projectId: Optional[str] = None
    tableId: Optional[str] = None


class ForeignKey(BaseModel):
    columnReferences: Optional[List[ColumnReference]] = Field(
        None, description="Required. The columns that compose the foreign key."
    )
    name: Optional[str] = Field(
        None, description="Optional. Set only if the foreign key constraint is named."
    )
    referencedTable: Optional[ReferencedTable] = None


class PrimaryKey(BaseModel):
    columns: Optional[List[str]] = Field(
        None,
        description="Required. The columns that are composed of the primary key constraint.",
    )


class TableConstraints(BaseModel):
    foreignKeys: Optional[List[ForeignKey]] = Field(
        None,
        description="Optional. Present only if the table has a foreign key. The foreign key is not enforced.",
    )
    primaryKey: Optional[PrimaryKey] = Field(
        None, description="Represents the primary key constraint on a table's columns."
    )


class InsertError(BaseModel):
    errors: Optional[List[ErrorProto]] = Field(
        None,
        description="Error information for the row indicated by the index property.",
    )
    index: Optional[int] = Field(
        None, description="The index of the row that error applies to."
    )


class TableDataInsertAllResponse(BaseModel):
    insertErrors: Optional[List[InsertError]] = Field(
        None,
        description="Describes specific errors encountered while processing the request.",
    )
    kind: Optional[str] = Field(
        "bigquery#tableDataInsertAllResponse",
        description='Returns "bigquery#tableDataInsertAllResponse".',
    )


class Categories(BaseModel):
    names: Optional[List[str]] = Field(None, description="Deprecated.")


class PolicyTags(BaseModel):
    names: Optional[List[str]] = Field(
        None,
        description='A list of policy tag resource names. For example, "projects/1/locations/eu/taxonomies/2/policyTags/3". At most 1 policy tag is currently allowed.',
    )


class RangeElementType(BaseModel):
    type: Optional[str] = Field(
        None,
        description="Required. The type of a field element. For more information, see TableFieldSchema.type.",
    )


class RoundingMode(Enum):
    ROUNDING_MODE_UNSPECIFIED = "ROUNDING_MODE_UNSPECIFIED"
    ROUND_HALF_AWAY_FROM_ZERO = "ROUND_HALF_AWAY_FROM_ZERO"
    ROUND_HALF_EVEN = "ROUND_HALF_EVEN"


class TableFieldSchema(BaseModel):
    categories: Optional[Categories] = Field(None, description="Deprecated.")
    collation: Optional[str] = Field(
        None,
        description="Optional. Field collation can be set only when the type of field is STRING. The following values are supported: * 'und:ci': undetermined locale, case insensitive. * '': empty string. Default to case-sensitive behavior.",
    )
    dataPolicies: Optional[List[DataPolicyOption]] = Field(
        None,
        description="Optional. Data policy options, will replace the data_policies.",
    )
    defaultValueExpression: Optional[str] = Field(
        None,
        description="Optional. A SQL expression to specify the [default value] (https://cloud.google.com/bigquery/docs/default-values) for this field.",
    )
    description: Optional[str] = Field(
        None,
        description="Optional. The field description. The maximum length is 1,024 characters.",
    )
    fields: Optional[List[TableFieldSchema]] = Field(
        None,
        description="Optional. Describes the nested schema fields if the type property is set to RECORD.",
    )
    foreignTypeDefinition: Optional[str] = Field(
        None,
        description="Optional. Definition of the foreign data type. Only valid for top-level schema fields (not nested fields). If the type is FOREIGN, this field is required.",
    )
    maxLength: Optional[str] = Field(
        None,
        description='Optional. Maximum length of values of this field for STRINGS or BYTES. If max_length is not specified, no maximum length constraint is imposed on this field. If type = "STRING", then max_length represents the maximum UTF-8 length of strings in this field. If type = "BYTES", then max_length represents the maximum number of bytes in this field. It is invalid to set this field if type ≠ "STRING" and ≠ "BYTES".',
    )
    mode: Optional[str] = Field(
        None,
        description="Optional. The field mode. Possible values include NULLABLE, REQUIRED and REPEATED. The default value is NULLABLE.",
    )
    name: Optional[str] = Field(
        None,
        description="Required. The field name. The name must contain only letters (a-z, A-Z), numbers (0-9), or underscores (_), and must start with a letter or underscore. The maximum length is 300 characters.",
    )
    policyTags: Optional[PolicyTags] = Field(
        None,
        description="Optional. The policy tags attached to this field, used for field-level access control. If not set, defaults to empty policy_tags.",
    )
    precision: Optional[str] = Field(
        None,
        description='Optional. Precision (maximum number of total digits in base 10) and scale (maximum number of digits in the fractional part in base 10) constraints for values of this field for NUMERIC or BIGNUMERIC. It is invalid to set precision or scale if type ≠ "NUMERIC" and ≠ "BIGNUMERIC". If precision and scale are not specified, no value range constraint is imposed on this field insofar as values are permitted by the type. Values of this NUMERIC or BIGNUMERIC field must be in this range when: * Precision (P) and scale (S) are specified: [-10P-S + 10-S, 10P-S - 10-S] * Precision (P) is specified but not scale (and thus scale is interpreted to be equal to zero): [-10P + 1, 10P - 1]. Acceptable values for precision and scale if both are specified: * If type = "NUMERIC": 1 ≤ precision - scale ≤ 29 and 0 ≤ scale ≤ 9. * If type = "BIGNUMERIC": 1 ≤ precision - scale ≤ 38 and 0 ≤ scale ≤ 38. Acceptable values for precision if only precision is specified but not scale (and thus scale is interpreted to be equal to zero): * If type = "NUMERIC": 1 ≤ precision ≤ 29. * If type = "BIGNUMERIC": 1 ≤ precision ≤ 38. If scale is specified but not precision, then it is invalid.',
    )
    rangeElementType: Optional[RangeElementType] = Field(
        None, description="Represents the type of a field element."
    )
    roundingMode: Optional[RoundingMode] = Field(
        None,
        description="Optional. Specifies the rounding mode to be used when storing values of NUMERIC and BIGNUMERIC type.",
    )
    scale: Optional[str] = Field(
        None, description="Optional. See documentation for precision."
    )
    type: Optional[str] = Field(
        None,
        description="Required. The field data type. Possible values include: * STRING * BYTES * INTEGER (or INT64) * FLOAT (or FLOAT64) * BOOLEAN (or BOOL) * TIMESTAMP * DATE * TIME * DATETIME * GEOGRAPHY * NUMERIC * BIGNUMERIC * JSON * RECORD (or STRUCT) * RANGE Use of RECORD/STRUCT indicates that the field contains a nested schema.",
    )


class View(BaseModel):
    privacyPolicy: Optional[PrivacyPolicy] = Field(
        None, description="Specifies the privacy policy for the view."
    )
    useLegacySql: Optional[bool] = Field(
        None,
        description="True if view is defined in legacy SQL dialect, false if in GoogleSQL.",
    )


class UnusedReason(Enum):
    UNUSED_REASON_UNSPECIFIED = "UNUSED_REASON_UNSPECIFIED"
    EXCEEDED_MAX_STALENESS = "EXCEEDED_MAX_STALENESS"
    METADATA_CACHING_NOT_ENABLED = "METADATA_CACHING_NOT_ENABLED"
    OTHER_REASON = "OTHER_REASON"


class TableReference(BaseModel):
    datasetId: Optional[str] = Field(
        None, description="Required. The ID of the dataset containing this table."
    )
    projectId: Optional[str] = Field(
        None, description="Required. The ID of the project containing this table."
    )
    tableId: Optional[str] = Field(
        None,
        description="Required. The ID of the table. The ID can contain Unicode characters in category L (letter), M (mark), N (number), Pc (connector, including underscore), Pd (dash), and Zs (space). For more information, see [General Category](https://wikipedia.org/wiki/Unicode_character_property#General_Category). The maximum length is 1,024 characters. Certain operations allow suffixing of the table ID with a partition decorator, such as `sample_table$20190123`.",
    )


class ReplicationStatus(Enum):
    REPLICATION_STATUS_UNSPECIFIED = "REPLICATION_STATUS_UNSPECIFIED"
    ACTIVE = "ACTIVE"
    SOURCE_DELETED = "SOURCE_DELETED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNSUPPORTED_CONFIGURATION = "UNSUPPORTED_CONFIGURATION"


class TableReplicationInfo(BaseModel):
    replicatedSourceLastRefreshTime: Optional[str] = Field(
        None,
        description="Optional. Output only. If source is a materialized view, this field signifies the last refresh time of the source.",
    )
    replicationError: Optional[ErrorProto] = Field(
        None,
        description="Optional. Output only. Replication error that will permanently stopped table replication.",
    )
    replicationIntervalMs: Optional[str] = Field(
        None,
        description="Optional. Specifies the interval at which the source table is polled for updates. It's Optional. If not specified, default replication interval would be applied.",
    )
    replicationStatus: Optional[ReplicationStatus] = Field(
        None,
        description="Optional. Output only. Replication status of configured replication.",
    )
    sourceTable: Optional[TableReference] = Field(
        None, description="Required. Source table reference that is replicated."
    )


class TableRow(BaseModel):
    f: Optional[List[TableCell]] = Field(
        None,
        description="Represents a single row in the result set, consisting of one or more fields.",
    )


class TableSchema(BaseModel):
    fields: Optional[List[TableFieldSchema]] = Field(
        None, description="Describes the fields in a table."
    )
    foreignTypeInfo: Optional[ForeignTypeInfo] = Field(
        None,
        description="Optional. Specifies metadata of the foreign data type definition in field schema (TableFieldSchema.foreign_type_definition).",
    )


class TestIamPermissionsRequest(BaseModel):
    permissions: Optional[List[str]] = Field(
        None,
        description="The set of permissions to check for the `resource`. Permissions with wildcards (such as `*` or `storage.*`) are not allowed. For more information see [IAM Overview](https://cloud.google.com/iam/docs/overview#permissions).",
    )


class TestIamPermissionsResponse(BaseModel):
    permissions: Optional[List[str]] = Field(
        None,
        description="A subset of `TestPermissionsRequest.permissions` that the caller is allowed.",
    )


class TimePartitioning(BaseModel):
    expirationMs: Optional[str] = Field(
        None,
        description="Optional. Number of milliseconds for which to keep the storage for a partition. A wrapper is used here because 0 is an invalid value.",
    )
    field: Optional[str] = Field(
        None,
        description="Optional. If not set, the table is partitioned by pseudo column '_PARTITIONTIME'; if set, the table is partitioned by this field. The field must be a top-level TIMESTAMP or DATE field. Its mode must be NULLABLE or REQUIRED. A wrapper is used here because an empty string is an invalid value.",
    )
    requirePartitionFilter: Optional[bool] = Field(
        False,
        description="If set to true, queries over this table require a partition filter that can be used for partition elimination to be specified. This field is deprecated; please set the field with the same name on the table itself instead. This field needs a wrapper because we want to output the default value, false, if the user explicitly set it.",
    )
    type: Optional[str] = Field(
        None,
        description="Required. The supported types are DAY, HOUR, MONTH, and YEAR, which will generate one partition per day, hour, month, and year, respectively.",
    )


class BoosterType(Enum):
    BOOSTER_TYPE_UNSPECIFIED = "BOOSTER_TYPE_UNSPECIFIED"
    GBTREE = "GBTREE"
    DART = "DART"


class CategoryEncodingMethod(Enum):
    ENCODING_METHOD_UNSPECIFIED = "ENCODING_METHOD_UNSPECIFIED"
    ONE_HOT_ENCODING = "ONE_HOT_ENCODING"
    LABEL_ENCODING = "LABEL_ENCODING"
    DUMMY_ENCODING = "DUMMY_ENCODING"


class ColorSpace(Enum):
    COLOR_SPACE_UNSPECIFIED = "COLOR_SPACE_UNSPECIFIED"
    RGB = "RGB"
    HSV = "HSV"
    YIQ = "YIQ"
    YUV = "YUV"
    GRAYSCALE = "GRAYSCALE"


class DartNormalizeType(Enum):
    DART_NORMALIZE_TYPE_UNSPECIFIED = "DART_NORMALIZE_TYPE_UNSPECIFIED"
    TREE = "TREE"
    FOREST = "FOREST"


class DataFrequency(Enum):
    DATA_FREQUENCY_UNSPECIFIED = "DATA_FREQUENCY_UNSPECIFIED"
    AUTO_FREQUENCY = "AUTO_FREQUENCY"
    YEARLY = "YEARLY"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"
    HOURLY = "HOURLY"
    PER_MINUTE = "PER_MINUTE"


class DataSplitMethod(Enum):
    DATA_SPLIT_METHOD_UNSPECIFIED = "DATA_SPLIT_METHOD_UNSPECIFIED"
    RANDOM = "RANDOM"
    CUSTOM = "CUSTOM"
    SEQUENTIAL = "SEQUENTIAL"
    NO_SPLIT = "NO_SPLIT"
    AUTO_SPLIT = "AUTO_SPLIT"


class DistanceType(Enum):
    DISTANCE_TYPE_UNSPECIFIED = "DISTANCE_TYPE_UNSPECIFIED"
    EUCLIDEAN = "EUCLIDEAN"
    COSINE = "COSINE"


class FeedbackType(Enum):
    FEEDBACK_TYPE_UNSPECIFIED = "FEEDBACK_TYPE_UNSPECIFIED"
    IMPLICIT = "IMPLICIT"
    EXPLICIT = "EXPLICIT"


class HolidayRegion(Enum):
    HOLIDAY_REGION_UNSPECIFIED = "HOLIDAY_REGION_UNSPECIFIED"
    GLOBAL = "GLOBAL"
    NA = "NA"
    JAPAC = "JAPAC"
    EMEA = "EMEA"
    LAC = "LAC"
    AE = "AE"
    AR = "AR"
    AT = "AT"
    AU = "AU"
    BE = "BE"
    BR = "BR"
    CA = "CA"
    CH = "CH"
    CL = "CL"
    CN = "CN"
    CO = "CO"
    CS = "CS"
    CZ = "CZ"
    DE = "DE"
    DK = "DK"
    DZ = "DZ"
    EC = "EC"
    EE = "EE"
    EG = "EG"
    ES = "ES"
    FI = "FI"
    FR = "FR"
    GB = "GB"
    GR = "GR"
    HK = "HK"
    HU = "HU"
    ID = "ID"
    IE = "IE"
    IL = "IL"
    IN = "IN"
    IR = "IR"
    IT = "IT"
    JP = "JP"
    KR = "KR"
    LV = "LV"
    MA = "MA"
    MX = "MX"
    MY = "MY"
    NG = "NG"
    NL = "NL"
    NO = "NO"
    NZ = "NZ"
    PE = "PE"
    PH = "PH"
    PK = "PK"
    PL = "PL"
    PT = "PT"
    RO = "RO"
    RS = "RS"
    RU = "RU"
    SA = "SA"
    SE = "SE"
    SG = "SG"
    SI = "SI"
    SK = "SK"
    TH = "TH"
    TR = "TR"
    TW = "TW"
    UA = "UA"
    US = "US"
    VE = "VE"
    VN = "VN"
    ZA = "ZA"


class HparamTuningObjective(Enum):
    HPARAM_TUNING_OBJECTIVE_UNSPECIFIED = "HPARAM_TUNING_OBJECTIVE_UNSPECIFIED"
    MEAN_ABSOLUTE_ERROR = "MEAN_ABSOLUTE_ERROR"
    MEAN_SQUARED_ERROR = "MEAN_SQUARED_ERROR"
    MEAN_SQUARED_LOG_ERROR = "MEAN_SQUARED_LOG_ERROR"
    MEDIAN_ABSOLUTE_ERROR = "MEDIAN_ABSOLUTE_ERROR"
    R_SQUARED = "R_SQUARED"
    EXPLAINED_VARIANCE = "EXPLAINED_VARIANCE"
    PRECISION = "PRECISION"
    RECALL = "RECALL"
    ACCURACY = "ACCURACY"
    F1_SCORE = "F1_SCORE"
    LOG_LOSS = "LOG_LOSS"
    ROC_AUC = "ROC_AUC"
    DAVIES_BOULDIN_INDEX = "DAVIES_BOULDIN_INDEX"
    MEAN_AVERAGE_PRECISION = "MEAN_AVERAGE_PRECISION"
    NORMALIZED_DISCOUNTED_CUMULATIVE_GAIN = "NORMALIZED_DISCOUNTED_CUMULATIVE_GAIN"
    AVERAGE_RANK = "AVERAGE_RANK"


class KmeansInitializationMethod(Enum):
    KMEANS_INITIALIZATION_METHOD_UNSPECIFIED = (
        "KMEANS_INITIALIZATION_METHOD_UNSPECIFIED"
    )
    RANDOM = "RANDOM"
    CUSTOM = "CUSTOM"
    KMEANS_PLUS_PLUS = "KMEANS_PLUS_PLUS"


class LearnRateStrategy(Enum):
    LEARN_RATE_STRATEGY_UNSPECIFIED = "LEARN_RATE_STRATEGY_UNSPECIFIED"
    LINE_SEARCH = "LINE_SEARCH"
    CONSTANT = "CONSTANT"


class LossType(Enum):
    LOSS_TYPE_UNSPECIFIED = "LOSS_TYPE_UNSPECIFIED"
    MEAN_SQUARED_LOSS = "MEAN_SQUARED_LOSS"
    MEAN_LOG_LOSS = "MEAN_LOG_LOSS"


class ModelRegistry(Enum):
    MODEL_REGISTRY_UNSPECIFIED = "MODEL_REGISTRY_UNSPECIFIED"
    VERTEX_AI = "VERTEX_AI"


class OptimizationStrategy(Enum):
    OPTIMIZATION_STRATEGY_UNSPECIFIED = "OPTIMIZATION_STRATEGY_UNSPECIFIED"
    BATCH_GRADIENT_DESCENT = "BATCH_GRADIENT_DESCENT"
    NORMAL_EQUATION = "NORMAL_EQUATION"


class PcaSolver(Enum):
    UNSPECIFIED = "UNSPECIFIED"
    FULL = "FULL"
    RANDOMIZED = "RANDOMIZED"
    AUTO = "AUTO"


class TreeMethod(Enum):
    TREE_METHOD_UNSPECIFIED = "TREE_METHOD_UNSPECIFIED"
    AUTO = "AUTO"
    EXACT = "EXACT"
    APPROX = "APPROX"
    HIST = "HIST"


class TrainingOptionsModel(BaseModel):
    activationFn: Optional[str] = Field(
        None, description="Activation function of the neural nets."
    )
    adjustStepChanges: Optional[bool] = Field(
        None,
        description="If true, detect step changes and make data adjustment in the input time series.",
    )
    approxGlobalFeatureContrib: Optional[bool] = Field(
        None,
        description="Whether to use approximate feature contribution method in XGBoost model explanation for global explain.",
    )
    autoArima: Optional[bool] = Field(
        None, description="Whether to enable auto ARIMA or not."
    )
    autoArimaMaxOrder: Optional[str] = Field(
        None, description="The max value of the sum of non-seasonal p and q."
    )
    autoArimaMinOrder: Optional[str] = Field(
        None, description="The min value of the sum of non-seasonal p and q."
    )
    autoClassWeights: Optional[bool] = Field(
        None,
        description="Whether to calculate class weights automatically based on the popularity of each label.",
    )
    batchSize: Optional[str] = Field(None, description="Batch size for dnn models.")
    boosterType: Optional[BoosterType] = Field(
        None, description="Booster type for boosted tree models."
    )
    budgetHours: Optional[float] = Field(
        None, description="Budget in hours for AutoML training."
    )
    calculatePValues: Optional[bool] = Field(
        None,
        description="Whether or not p-value test should be computed for this model. Only available for linear and logistic regression models.",
    )
    categoryEncodingMethod: Optional[CategoryEncodingMethod] = Field(
        None, description="Categorical feature encoding method."
    )
    cleanSpikesAndDips: Optional[bool] = Field(
        None, description="If true, clean spikes and dips in the input time series."
    )
    colorSpace: Optional[ColorSpace] = Field(
        None,
        description="Enums for color space, used for processing images in Object Table. See more details at https://www.tensorflow.org/io/tutorials/colorspace.",
    )
    colsampleBylevel: Optional[float] = Field(
        None,
        description="Subsample ratio of columns for each level for boosted tree models.",
    )
    colsampleBynode: Optional[float] = Field(
        None,
        description="Subsample ratio of columns for each node(split) for boosted tree models.",
    )
    colsampleBytree: Optional[float] = Field(
        None,
        description="Subsample ratio of columns when constructing each tree for boosted tree models.",
    )
    contributionMetric: Optional[str] = Field(
        None,
        description="The contribution metric. Applies to contribution analysis models. Allowed formats supported are for summable and summable ratio contribution metrics. These include expressions such as `SUM(x)` or `SUM(x)/SUM(y)`, where x and y are column names from the base table.",
    )
    dartNormalizeType: Optional[DartNormalizeType] = Field(
        None,
        description="Type of normalization algorithm for boosted tree models using dart booster.",
    )
    dataFrequency: Optional[DataFrequency] = Field(
        None, description="The data frequency of a time series."
    )
    dataSplitColumn: Optional[str] = Field(
        None,
        description="The column to split data with. This column won't be used as a feature. 1. When data_split_method is CUSTOM, the corresponding column should be boolean. The rows with true value tag are eval data, and the false are training data. 2. When data_split_method is SEQ, the first DATA_SPLIT_EVAL_FRACTION rows (from smallest to largest) in the corresponding column are used as training data, and the rest are eval data. It respects the order in Orderable data types: https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types#data_type_properties",
    )
    dataSplitEvalFraction: Optional[float] = Field(
        None,
        description="The fraction of evaluation data over the whole input data. The rest of data will be used as training data. The format should be double. Accurate to two decimal places. Default value is 0.2.",
    )
    dataSplitMethod: Optional[DataSplitMethod] = Field(
        None,
        description="The data split type for training and evaluation, e.g. RANDOM.",
    )
    decomposeTimeSeries: Optional[bool] = Field(
        None, description="If true, perform decompose time series and save the results."
    )
    dimensionIdColumns: Optional[List[str]] = Field(
        None,
        description="Optional. Names of the columns to slice on. Applies to contribution analysis models.",
    )
    distanceType: Optional[DistanceType] = Field(
        None, description="Distance type for clustering models."
    )
    dropout: Optional[float] = Field(
        None, description="Dropout probability for dnn models."
    )
    earlyStop: Optional[bool] = Field(
        None,
        description="Whether to stop early when the loss doesn't improve significantly any more (compared to min_relative_progress). Used only for iterative training algorithms.",
    )
    enableGlobalExplain: Optional[bool] = Field(
        None, description="If true, enable global explanation during training."
    )
    feedbackType: Optional[FeedbackType] = Field(
        None,
        description="Feedback type that specifies which algorithm to run for matrix factorization.",
    )
    fitIntercept: Optional[bool] = Field(
        None,
        description="Whether the model should include intercept during model training.",
    )
    forecastLimitLowerBound: Optional[float] = Field(
        None,
        description="The forecast limit lower bound that was used during ARIMA model training with limits. To see more details of the algorithm: https://otexts.com/fpp2/limits.html",
    )
    forecastLimitUpperBound: Optional[float] = Field(
        None,
        description="The forecast limit upper bound that was used during ARIMA model training with limits.",
    )
    hiddenUnits: Optional[List[str]] = Field(
        None, description="Hidden units for dnn models."
    )
    holidayRegion: Optional[HolidayRegion] = Field(
        None,
        description="The geographical region based on which the holidays are considered in time series modeling. If a valid value is specified, then holiday effects modeling is enabled.",
    )
    holidayRegions: Optional[List[HolidayRegion]] = Field(
        None,
        description="A list of geographical regions that are used for time series modeling.",
    )
    horizon: Optional[str] = Field(
        None, description="The number of periods ahead that need to be forecasted."
    )
    hparamTuningObjectives: Optional[List[HparamTuningObjective]] = Field(
        None,
        description="The target evaluation metrics to optimize the hyperparameters for.",
    )
    includeDrift: Optional[bool] = Field(
        None, description="Include drift when fitting an ARIMA model."
    )
    initialLearnRate: Optional[float] = Field(
        None,
        description="Specifies the initial learning rate for the line search learn rate strategy.",
    )
    inputLabelColumns: Optional[List[str]] = Field(
        None, description="Name of input label columns in training data."
    )
    instanceWeightColumn: Optional[str] = Field(
        None,
        description="Name of the instance weight column for training data. This column isn't be used as a feature.",
    )
    integratedGradientsNumSteps: Optional[str] = Field(
        None,
        description="Number of integral steps for the integrated gradients explain method.",
    )
    isTestColumn: Optional[str] = Field(
        None,
        description="Name of the column used to determine the rows corresponding to control and test. Applies to contribution analysis models.",
    )
    itemColumn: Optional[str] = Field(
        None, description="Item column specified for matrix factorization models."
    )
    kmeansInitializationColumn: Optional[str] = Field(
        None,
        description="The column used to provide the initial centroids for kmeans algorithm when kmeans_initialization_method is CUSTOM.",
    )
    kmeansInitializationMethod: Optional[KmeansInitializationMethod] = Field(
        None,
        description="The method used to initialize the centroids for kmeans algorithm.",
    )
    l1RegActivation: Optional[float] = Field(
        None, description="L1 regularization coefficient to activations."
    )
    l1Regularization: Optional[float] = Field(
        None, description="L1 regularization coefficient."
    )
    l2Regularization: Optional[float] = Field(
        None, description="L2 regularization coefficient."
    )
    labelClassWeights: Optional[Dict[str, float]] = Field(
        None,
        description="Weights associated with each label class, for rebalancing the training data. Only applicable for classification models.",
    )
    learnRate: Optional[float] = Field(
        None,
        description="Learning rate in training. Used only for iterative training algorithms.",
    )
    learnRateStrategy: Optional[LearnRateStrategy] = Field(
        None,
        description="The strategy to determine learn rate for the current iteration.",
    )
    lossType: Optional[LossType] = Field(
        None, description="Type of loss function used during training run."
    )
    maxIterations: Optional[str] = Field(
        None,
        description="The maximum number of iterations in training. Used only for iterative training algorithms.",
    )
    maxParallelTrials: Optional[str] = Field(
        None, description="Maximum number of trials to run in parallel."
    )
    maxTimeSeriesLength: Optional[str] = Field(
        None,
        description="The maximum number of time points in a time series that can be used in modeling the trend component of the time series. Don't use this option with the `timeSeriesLengthFraction` or `minTimeSeriesLength` options.",
    )
    maxTreeDepth: Optional[str] = Field(
        None, description="Maximum depth of a tree for boosted tree models."
    )
    minAprioriSupport: Optional[float] = Field(
        None,
        description="The apriori support minimum. Applies to contribution analysis models.",
    )
    minRelativeProgress: Optional[float] = Field(
        None,
        description="When early_stop is true, stops training when accuracy improvement is less than 'min_relative_progress'. Used only for iterative training algorithms.",
    )
    minSplitLoss: Optional[float] = Field(
        None, description="Minimum split loss for boosted tree models."
    )
    minTimeSeriesLength: Optional[str] = Field(
        None,
        description="The minimum number of time points in a time series that are used in modeling the trend component of the time series. If you use this option you must also set the `timeSeriesLengthFraction` option. This training option ensures that enough time points are available when you use `timeSeriesLengthFraction` in trend modeling. This is particularly important when forecasting multiple time series in a single query using `timeSeriesIdColumn`. If the total number of time points is less than the `minTimeSeriesLength` value, then the query uses all available time points.",
    )
    minTreeChildWeight: Optional[str] = Field(
        None,
        description="Minimum sum of instance weight needed in a child for boosted tree models.",
    )
    modelRegistry: Optional[ModelRegistry] = Field(
        None, description="The model registry."
    )
    modelUri: Optional[str] = Field(
        None,
        description="Google Cloud Storage URI from which the model was imported. Only applicable for imported models.",
    )
    nonSeasonalOrder: Optional[ArimaOrder] = Field(
        None,
        description="A specification of the non-seasonal part of the ARIMA model: the three components (p, d, q) are the AR order, the degree of differencing, and the MA order.",
    )
    numClusters: Optional[str] = Field(
        None, description="Number of clusters for clustering models."
    )
    numFactors: Optional[str] = Field(
        None, description="Num factors specified for matrix factorization models."
    )
    numParallelTree: Optional[str] = Field(
        None,
        description="Number of parallel trees constructed during each iteration for boosted tree models.",
    )
    numPrincipalComponents: Optional[str] = Field(
        None,
        description="Number of principal components to keep in the PCA model. Must be <= the number of features.",
    )
    numTrials: Optional[str] = Field(
        None, description="Number of trials to run this hyperparameter tuning job."
    )
    optimizationStrategy: Optional[OptimizationStrategy] = Field(
        None, description="Optimization strategy for training linear regression models."
    )
    optimizer: Optional[str] = Field(
        None, description="Optimizer used for training the neural nets."
    )
    pcaExplainedVarianceRatio: Optional[float] = Field(
        None,
        description="The minimum ratio of cumulative explained variance that needs to be given by the PCA model.",
    )
    pcaSolver: Optional[PcaSolver] = Field(None, description="The solver for PCA.")
    sampledShapleyNumPaths: Optional[str] = Field(
        None, description="Number of paths for the sampled Shapley explain method."
    )
    scaleFeatures: Optional[bool] = Field(
        None,
        description="If true, scale the feature values by dividing the feature standard deviation. Currently only apply to PCA.",
    )
    standardizeFeatures: Optional[bool] = Field(
        None, description="Whether to standardize numerical features. Default to true."
    )
    subsample: Optional[float] = Field(
        None,
        description="Subsample fraction of the training data to grow tree to prevent overfitting for boosted tree models.",
    )
    tfVersion: Optional[str] = Field(
        None,
        description="Based on the selected TF version, the corresponding docker image is used to train external models.",
    )
    timeSeriesDataColumn: Optional[str] = Field(
        None, description="Column to be designated as time series data for ARIMA model."
    )
    timeSeriesIdColumn: Optional[str] = Field(
        None,
        description="The time series id column that was used during ARIMA model training.",
    )
    timeSeriesIdColumns: Optional[List[str]] = Field(
        None,
        description="The time series id columns that were used during ARIMA model training.",
    )
    timeSeriesLengthFraction: Optional[float] = Field(
        None,
        description="The fraction of the interpolated length of the time series that's used to model the time series trend component. All of the time points of the time series are used to model the non-trend component. This training option accelerates modeling training without sacrificing much forecasting accuracy. You can use this option with `minTimeSeriesLength` but not with `maxTimeSeriesLength`.",
    )
    timeSeriesTimestampColumn: Optional[str] = Field(
        None,
        description="Column to be designated as time series timestamp for ARIMA model.",
    )
    treeMethod: Optional[TreeMethod] = Field(
        None, description="Tree construction algorithm for boosted tree models."
    )
    trendSmoothingWindowSize: Optional[str] = Field(
        None,
        description="Smoothing window size for the trend component. When a positive value is specified, a center moving average smoothing is applied on the history trend. When the smoothing window is out of the boundary at the beginning or the end of the trend, the first element or the last element is padded to fill the smoothing window before the average is applied.",
    )
    userColumn: Optional[str] = Field(
        None, description="User column specified for matrix factorization models."
    )
    vertexAiModelVersionAliases: Optional[List[str]] = Field(
        None,
        description="The version aliases to apply in Vertex AI model registry. Always overwrite if the version aliases exists in a existing model.",
    )
    walsAlpha: Optional[float] = Field(
        None,
        description="Hyperparameter for matrix factoration when implicit feedback type is specified.",
    )
    warmStart: Optional[bool] = Field(
        None, description="Whether to train a model from the last checkpoint."
    )
    xgboostVersion: Optional[str] = Field(
        None,
        description="User-selected XGBoost versions for training of XGBoost models.",
    )


class TransactionInfo(BaseModel):
    transactionId: Optional[str] = Field(
        None, description="Output only. [Alpha] Id of the transaction."
    )


class UndeleteDatasetRequest(BaseModel):
    deletionTime: Optional[str] = Field(
        None,
        description="Optional. The exact time when the dataset was deleted. If not specified, the most recently deleted version is undeleted. Undeleting a dataset using deletion time is not supported.",
    )


class UserDefinedFunctionResource(BaseModel):
    inlineCode: Optional[str] = Field(
        None,
        description="[Pick one] An inline resource that contains code for a user-defined function (UDF). Providing a inline code resource is equivalent to providing a URI for a file containing the same code.",
    )
    resourceUri: Optional[str] = Field(
        None,
        description="[Pick one] A code resource to load from a Google Cloud Storage URI (gs://bucket/path).",
    )


class ViewDefinition(BaseModel):
    foreignDefinitions: Optional[List[ForeignViewDefinition]] = Field(
        None, description="Optional. Foreign view representations."
    )
    privacyPolicy: Optional[PrivacyPolicy] = Field(
        None, description="Optional. Specifies the privacy policy for the view."
    )
    query: Optional[str] = Field(
        None,
        description="Required. A query that BigQuery executes when the view is referenced.",
    )
    useExplicitColumnNames: Optional[bool] = Field(
        None,
        description="True if the column names are explicitly specified. For example by using the 'CREATE VIEW v(c1, c2) AS ...' syntax. Can only be set for GoogleSQL views.",
    )
    useLegacySql: Optional[bool] = Field(
        None,
        description="Specifies whether to use BigQuery's legacy SQL for this view. The default value is true. If set to false, the view will use BigQuery's GoogleSQL: https://cloud.google.com/bigquery/sql-reference/ Queries and views that reference this view must use the same flag value. A wrapper is used here because the default value is True.",
    )
    userDefinedFunctionResources: Optional[List[UserDefinedFunctionResource]] = Field(
        None, description="Describes user-defined function resources used in the query."
    )


class FieldXgafv(Enum):
    field_1 = "1"
    field_2 = "2"


class Alt(Enum):
    json = "json"
    media = "media"
    proto = "proto"


class DatasetView(Enum):
    DATASET_VIEW_UNSPECIFIED = "DATASET_VIEW_UNSPECIFIED"
    METADATA = "METADATA"
    ACL = "ACL"
    FULL = "FULL"


class View1(Enum):
    TABLE_METADATA_VIEW_UNSPECIFIED = "TABLE_METADATA_VIEW_UNSPECIFIED"
    BASIC = "BASIC"
    STORAGE_STATS = "STORAGE_STATS"
    FULL = "FULL"


class Projection(Enum):
    full = "full"
    minimal = "minimal"


class StateFilterEnum(Enum):
    done = "done"
    pending = "pending"
    running = "running"


class ArimaForecastingMetrics(BaseModel):
    arimaFittingMetrics: Optional[List[ArimaFittingMetrics]] = Field(
        None, description="Arima model fitting metrics."
    )
    arimaSingleModelForecastingMetrics: Optional[
        List[ArimaSingleModelForecastingMetrics]
    ] = Field(
        None,
        description="Repeated as there can be many metric sets (one for each model) in auto-arima and the large-scale case.",
    )
    hasDrift: Optional[List[bool]] = Field(
        None,
        description="Whether Arima model fitted with drift or not. It is always false when d is not 1.",
    )
    nonSeasonalOrder: Optional[List[ArimaOrder]] = Field(
        None, description="Non-seasonal order."
    )
    seasonalPeriods: Optional[List[SeasonalPeriod]] = Field(
        None,
        description="Seasonal periods. Repeated because multiple periods are supported for one time series.",
    )
    timeSeriesId: Optional[List[str]] = Field(
        None,
        description="Id to differentiate different time series for the large-scale case.",
    )


class ArimaModelInfo(BaseModel):
    arimaCoefficients: Optional[ArimaCoefficients] = Field(
        None, description="Arima coefficients."
    )
    arimaFittingMetrics: Optional[ArimaFittingMetrics] = Field(
        None, description="Arima fitting metrics."
    )
    hasDrift: Optional[bool] = Field(
        None,
        description="Whether Arima model fitted with drift or not. It is always false when d is not 1.",
    )
    hasHolidayEffect: Optional[bool] = Field(
        None,
        description="If true, holiday_effect is a part of time series decomposition result.",
    )
    hasSpikesAndDips: Optional[bool] = Field(
        None,
        description="If true, spikes_and_dips is a part of time series decomposition result.",
    )
    hasStepChanges: Optional[bool] = Field(
        None,
        description="If true, step_changes is a part of time series decomposition result.",
    )
    nonSeasonalOrder: Optional[ArimaOrder] = Field(
        None, description="Non-seasonal order."
    )
    seasonalPeriods: Optional[List[SeasonalPeriod]] = Field(
        None,
        description="Seasonal periods. Repeated because multiple periods are supported for one time series.",
    )
    timeSeriesId: Optional[str] = Field(
        None,
        description="The time_series_id value for this time series. It will be one of the unique values from the time_series_id_column specified during ARIMA model training. Only present when time_series_id_column training option was used.",
    )
    timeSeriesIds: Optional[List[str]] = Field(
        None,
        description="The tuple of time_series_ids identifying this time series. It will be one of the unique tuples of values present in the time_series_id_columns specified during ARIMA model training. Only present when time_series_id_columns training option was used and the order of values here are same as the order of time_series_id_columns.",
    )


class ArimaResult(BaseModel):
    arimaModelInfo: Optional[List[ArimaModelInfo]] = Field(
        None,
        description="This message is repeated because there are multiple arima models fitted in auto-arima. For non-auto-arima model, its size is one.",
    )
    seasonalPeriods: Optional[List[SeasonalPeriod]] = Field(
        None,
        description="Seasonal periods. Repeated because multiple periods are supported for one time series.",
    )


class AuditConfig(BaseModel):
    auditLogConfigs: Optional[List[AuditLogConfig]] = Field(
        None, description="The configuration for logging of each type of permission."
    )
    service: Optional[str] = Field(
        None,
        description="Specifies a service that will be enabled for audit logging. For example, `storage.googleapis.com`, `cloudsql.googleapis.com`. `allServices` is a special value that covers all services.",
    )


class BinaryClassificationMetrics(BaseModel):
    aggregateClassificationMetrics: Optional[AggregateClassificationMetrics] = Field(
        None, description="Aggregate classification metrics."
    )
    binaryConfusionMatrixList: Optional[List[BinaryConfusionMatrix]] = Field(
        None, description="Binary confusion matrix at multiple thresholds."
    )
    negativeLabel: Optional[str] = Field(
        None, description="Label representing the negative class."
    )
    positiveLabel: Optional[str] = Field(
        None, description="Label representing the positive class."
    )


class Binding(BaseModel):
    condition: Optional[Expr] = Field(
        None,
        description="The condition that is associated with this binding. If the condition evaluates to `true`, then this binding applies to the current request. If the condition evaluates to `false`, then this binding does not apply to the current request. However, a different role binding might grant the same role to one or more of the principals in this binding. To learn which resources support conditions in their IAM policies, see the [IAM documentation](https://cloud.google.com/iam/help/conditions/resource-policies).",
    )
    members: Optional[List[str]] = Field(
        None,
        description="Specifies the principals requesting access for a Google Cloud resource. `members` can have the following values: * `allUsers`: A special identifier that represents anyone who is on the internet; with or without a Google account. * `allAuthenticatedUsers`: A special identifier that represents anyone who is authenticated with a Google account or a service account. Does not include identities that come from external identity providers (IdPs) through identity federation. * `user:{emailid}`: An email address that represents a specific Google account. For example, `alice@example.com` . * `serviceAccount:{emailid}`: An email address that represents a Google service account. For example, `my-other-app@appspot.gserviceaccount.com`. * `serviceAccount:{projectid}.svc.id.goog[{namespace}/{kubernetes-sa}]`: An identifier for a [Kubernetes service account](https://cloud.google.com/kubernetes-engine/docs/how-to/kubernetes-service-accounts). For example, `my-project.svc.id.goog[my-namespace/my-kubernetes-sa]`. * `group:{emailid}`: An email address that represents a Google group. For example, `admins@example.com`. * `domain:{domain}`: The G Suite domain (primary) that represents all the users of that domain. For example, `google.com` or `example.com`. * `principal://iam.googleapis.com/locations/global/workforcePools/{pool_id}/subject/{subject_attribute_value}`: A single identity in a workforce identity pool. * `principalSet://iam.googleapis.com/locations/global/workforcePools/{pool_id}/group/{group_id}`: All workforce identities in a group. * `principalSet://iam.googleapis.com/locations/global/workforcePools/{pool_id}/attribute.{attribute_name}/{attribute_value}`: All workforce identities with a specific attribute value. * `principalSet://iam.googleapis.com/locations/global/workforcePools/{pool_id}/*`: All identities in a workforce identity pool. * `principal://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{pool_id}/subject/{subject_attribute_value}`: A single identity in a workload identity pool. * `principalSet://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{pool_id}/group/{group_id}`: A workload identity pool group. * `principalSet://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{pool_id}/attribute.{attribute_name}/{attribute_value}`: All identities in a workload identity pool with a certain attribute. * `principalSet://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{pool_id}/*`: All identities in a workload identity pool. * `deleted:user:{emailid}?uid={uniqueid}`: An email address (plus unique identifier) representing a user that has been recently deleted. For example, `alice@example.com?uid=123456789012345678901`. If the user is recovered, this value reverts to `user:{emailid}` and the recovered user retains the role in the binding. * `deleted:serviceAccount:{emailid}?uid={uniqueid}`: An email address (plus unique identifier) representing a service account that has been recently deleted. For example, `my-other-app@appspot.gserviceaccount.com?uid=123456789012345678901`. If the service account is undeleted, this value reverts to `serviceAccount:{emailid}` and the undeleted service account retains the role in the binding. * `deleted:group:{emailid}?uid={uniqueid}`: An email address (plus unique identifier) representing a Google group that has been recently deleted. For example, `admins@example.com?uid=123456789012345678901`. If the group is recovered, this value reverts to `group:{emailid}` and the recovered group retains the role in the binding. * `deleted:principal://iam.googleapis.com/locations/global/workforcePools/{pool_id}/subject/{subject_attribute_value}`: Deleted single identity in a workforce identity pool. For example, `deleted:principal://iam.googleapis.com/locations/global/workforcePools/my-pool-id/subject/my-subject-attribute-value`.",
    )
    role: Optional[str] = Field(
        None,
        description="Role that is assigned to the list of `members`, or principals. For example, `roles/viewer`, `roles/editor`, or `roles/owner`. For an overview of the IAM roles and permissions, see the [IAM documentation](https://cloud.google.com/iam/docs/roles-overview). For a list of the available pre-defined roles, see [here](https://cloud.google.com/iam/docs/understanding-roles).",
    )


class CategoricalValue(BaseModel):
    categoryCounts: Optional[List[CategoryCount]] = Field(
        None,
        description='Counts of all categories for the categorical feature. If there are more than ten categories, we return top ten (by count) and return one more CategoryCount with category "_OTHER_" and count as aggregate counts of remaining categories.',
    )


class CloneDefinition(BaseModel):
    baseTableReference: Optional[TableReference] = Field(
        None,
        description="Required. Reference describing the ID of the table that was cloned.",
    )
    cloneTime: Optional[AwareDatetime] = Field(
        None,
        description="Required. The time at which the base table was cloned. This value is reported in the JSON response using RFC3339 format.",
    )


class ConfusionMatrix(BaseModel):
    confidenceThreshold: Optional[float] = Field(
        None,
        description="Confidence threshold used when computing the entries of the confusion matrix.",
    )
    rows: Optional[List[Row]] = Field(None, description="One row per actual label.")


class DataSplitResult(BaseModel):
    evaluationTable: Optional[TableReference] = Field(
        None, description="Table reference of the evaluation data after split."
    )
    testTable: Optional[TableReference] = Field(
        None, description="Table reference of the test data after split."
    )
    trainingTable: Optional[TableReference] = Field(
        None, description="Table reference of the training data after split."
    )


class DatasetAccessEntry(BaseModel):
    dataset: Optional[DatasetReference] = Field(
        None, description="The dataset this entry applies to"
    )
    targetTypes: Optional[List[TargetType]] = Field(
        None,
        description="Which resources in the dataset this entry applies to. Currently, only views are supported, but additional target types may be added in the future.",
    )


class Dataset1(BaseModel):
    datasetReference: Optional[DatasetReference] = Field(
        None,
        description="The dataset reference. Use this property to access specific parts of the dataset's ID, such as project ID or dataset ID.",
    )
    friendlyName: Optional[str] = Field(
        None,
        description="An alternate name for the dataset. The friendly name is purely decorative in nature.",
    )
    id: Optional[str] = Field(
        None, description="The fully-qualified, unique, opaque ID of the dataset."
    )
    kind: Optional[str] = Field(
        None,
        description='The resource type. This property always returns the value "bigquery#dataset"',
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="The labels associated with this dataset. You can use these to organize and group your datasets.",
    )
    location: Optional[str] = Field(
        None, description="The geographic location where the dataset resides."
    )


class DatasetList(BaseModel):
    datasets: Optional[List[Dataset1]] = Field(
        None,
        description="An array of the dataset resources in the project. Each resource contains basic information. For full information about a particular dataset resource, use the Datasets: get method. This property is omitted when there are no datasets in the project.",
    )
    etag: Optional[str] = Field(
        None,
        description="Output only. A hash value of the results page. You can use this property to determine if the page has changed since the last request.",
    )
    kind: Optional[str] = Field(
        "bigquery#datasetList",
        description='Output only. The resource type. This property always returns the value "bigquery#datasetList"',
    )
    nextPageToken: Optional[str] = Field(
        None,
        description="A token that can be used to request the next results page. This property is omitted on the final results page.",
    )
    unreachable: Optional[List[str]] = Field(
        None,
        description='A list of skipped locations that were unreachable. For more information about BigQuery locations, see: https://cloud.google.com/bigquery/docs/locations. Example: "europe-west5"',
    )


class DoubleHparamSearchSpace(BaseModel):
    candidates: Optional[DoubleCandidates] = Field(
        None, description="Candidates of the double hyperparameter."
    )
    range: Optional[DoubleRange] = Field(
        None, description="Range of the double hyperparameter."
    )


class ExplainQueryStage(BaseModel):
    completedParallelInputs: Optional[str] = Field(
        None, description="Number of parallel input segments completed."
    )
    computeMode: Optional[ComputeMode] = Field(
        None, description="Output only. Compute mode for this stage."
    )
    computeMsAvg: Optional[str] = Field(
        None, description="Milliseconds the average shard spent on CPU-bound tasks."
    )
    computeMsMax: Optional[str] = Field(
        None, description="Milliseconds the slowest shard spent on CPU-bound tasks."
    )
    computeRatioAvg: Optional[float] = Field(
        None,
        description="Relative amount of time the average shard spent on CPU-bound tasks.",
    )
    computeRatioMax: Optional[float] = Field(
        None,
        description="Relative amount of time the slowest shard spent on CPU-bound tasks.",
    )
    endMs: Optional[str] = Field(
        None, description="Stage end time represented as milliseconds since the epoch."
    )
    id: Optional[str] = Field(
        None, description="Unique ID for the stage within the plan."
    )
    inputStages: Optional[List[str]] = Field(
        None, description="IDs for stages that are inputs to this stage."
    )
    name: Optional[str] = Field(None, description="Human-readable name for the stage.")
    parallelInputs: Optional[str] = Field(
        None, description="Number of parallel input segments to be processed"
    )
    readMsAvg: Optional[str] = Field(
        None, description="Milliseconds the average shard spent reading input."
    )
    readMsMax: Optional[str] = Field(
        None, description="Milliseconds the slowest shard spent reading input."
    )
    readRatioAvg: Optional[float] = Field(
        None,
        description="Relative amount of time the average shard spent reading input.",
    )
    readRatioMax: Optional[float] = Field(
        None,
        description="Relative amount of time the slowest shard spent reading input.",
    )
    recordsRead: Optional[str] = Field(
        None, description="Number of records read into the stage."
    )
    recordsWritten: Optional[str] = Field(
        None, description="Number of records written by the stage."
    )
    shuffleOutputBytes: Optional[str] = Field(
        None, description="Total number of bytes written to shuffle."
    )
    shuffleOutputBytesSpilled: Optional[str] = Field(
        None,
        description="Total number of bytes written to shuffle and spilled to disk.",
    )
    slotMs: Optional[str] = Field(
        None, description="Slot-milliseconds used by the stage."
    )
    startMs: Optional[str] = Field(
        None,
        description="Stage start time represented as milliseconds since the epoch.",
    )
    status: Optional[str] = Field(None, description="Current status for this stage.")
    steps: Optional[List[ExplainQueryStep]] = Field(
        None,
        description="List of operations within the stage in dependency order (approximately chronological).",
    )
    waitMsAvg: Optional[str] = Field(
        None,
        description="Milliseconds the average shard spent waiting to be scheduled.",
    )
    waitMsMax: Optional[str] = Field(
        None,
        description="Milliseconds the slowest shard spent waiting to be scheduled.",
    )
    waitRatioAvg: Optional[float] = Field(
        None,
        description="Relative amount of time the average shard spent waiting to be scheduled.",
    )
    waitRatioMax: Optional[float] = Field(
        None,
        description="Relative amount of time the slowest shard spent waiting to be scheduled.",
    )
    writeMsAvg: Optional[str] = Field(
        None, description="Milliseconds the average shard spent on writing output."
    )
    writeMsMax: Optional[str] = Field(
        None, description="Milliseconds the slowest shard spent on writing output."
    )
    writeRatioAvg: Optional[float] = Field(
        None,
        description="Relative amount of time the average shard spent on writing output.",
    )
    writeRatioMax: Optional[float] = Field(
        None,
        description="Relative amount of time the slowest shard spent on writing output.",
    )


class ExternalCatalogTableOptions(BaseModel):
    parameters: Optional[Dict[str, str]] = Field(
        None,
        description="Optional. A map of the key-value pairs defining the parameters and properties of the open source table. Corresponds with Hive metastore table parameters. Maximum size of 4MiB.",
    )
    connectionId: Optional[str] = Field(
        None,
        description="Optional. A connection ID that specifies the credentials to be used to read external storage, such as Azure Blob, Cloud Storage, or Amazon S3. This connection is needed to read the open source table from BigQuery. The connection_id format must be either `..` or `projects//locations//connections/`.",
    )
    storageDescriptor: Optional[StorageDescriptor] = Field(
        None,
        description="Optional. A storage descriptor containing information about the physical storage of this table.",
    )


class ExternalDataConfiguration(BaseModel):
    autodetect: Optional[bool] = Field(
        None,
        description="Try to detect schema and format options automatically. Any option specified explicitly will be honored.",
    )
    avroOptions: Optional[AvroOptions] = Field(
        None,
        description="Optional. Additional properties to set if sourceFormat is set to AVRO.",
    )
    bigtableOptions: Optional[BigtableOptions] = Field(
        None,
        description="Optional. Additional options if sourceFormat is set to BIGTABLE.",
    )
    compression: Optional[str] = Field(
        None,
        description="Optional. The compression type of the data source. Possible values include GZIP and NONE. The default value is NONE. This setting is ignored for Google Cloud Bigtable, Google Cloud Datastore backups, Avro, ORC and Parquet formats. An empty string is an invalid value.",
    )
    connectionId: Optional[str] = Field(
        None,
        description="Optional. The connection specifying the credentials to be used to read external storage, such as Azure Blob, Cloud Storage, or S3. The connection_id can have the form `{project_id}.{location_id};{connection_id}` or `projects/{project_id}/locations/{location_id}/connections/{connection_id}`.",
    )
    csvOptions: Optional[CsvOptions] = Field(
        None,
        description="Optional. Additional properties to set if sourceFormat is set to CSV.",
    )
    dateFormat: Optional[str] = Field(
        None,
        description="Optional. Format used to parse DATE values. Supports C-style and SQL-style values.",
    )
    datetimeFormat: Optional[str] = Field(
        None,
        description="Optional. Format used to parse DATETIME values. Supports C-style and SQL-style values.",
    )
    decimalTargetTypes: Optional[List[DecimalTargetType]] = Field(
        None,
        description='Defines the list of possible SQL data types to which the source decimal values are converted. This list and the precision and the scale parameters of the decimal field determine the target type. In the order of NUMERIC, BIGNUMERIC, and STRING, a type is picked if it is in the specified list and if it supports the precision and the scale. STRING supports all precision and scale values. If none of the listed types supports the precision and the scale, the type supporting the widest range in the specified list is picked, and if a value exceeds the supported range when reading the data, an error will be thrown. Example: Suppose the value of this field is ["NUMERIC", "BIGNUMERIC"]. If (precision,scale) is: * (38,9) -> NUMERIC; * (39,9) -> BIGNUMERIC (NUMERIC cannot hold 30 integer digits); * (38,10) -> BIGNUMERIC (NUMERIC cannot hold 10 fractional digits); * (76,38) -> BIGNUMERIC; * (77,38) -> BIGNUMERIC (error if value exceeds supported range). This field cannot contain duplicate types. The order of the types in this field is ignored. For example, ["BIGNUMERIC", "NUMERIC"] is the same as ["NUMERIC", "BIGNUMERIC"] and NUMERIC always takes precedence over BIGNUMERIC. Defaults to ["NUMERIC", "STRING"] for ORC and ["NUMERIC"] for the other file formats.',
    )
    fileSetSpecType: Optional[FileSetSpecType] = Field(
        None,
        description="Optional. Specifies how source URIs are interpreted for constructing the file set to load. By default source URIs are expanded against the underlying storage. Other options include specifying manifest files. Only applicable to object storage systems.",
    )
    googleSheetsOptions: Optional[GoogleSheetsOptions] = Field(
        None,
        description="Optional. Additional options if sourceFormat is set to GOOGLE_SHEETS.",
    )
    hivePartitioningOptions: Optional[HivePartitioningOptions] = Field(
        None,
        description="Optional. When set, configures hive partitioning support. Not all storage formats support hive partitioning -- requesting hive partitioning on an unsupported format will lead to an error, as will providing an invalid specification.",
    )
    ignoreUnknownValues: Optional[bool] = Field(
        None,
        description="Optional. Indicates if BigQuery should allow extra values that are not represented in the table schema. If true, the extra values are ignored. If false, records with extra columns are treated as bad records, and if there are too many bad records, an invalid error is returned in the job result. The default value is false. The sourceFormat property determines what BigQuery treats as an extra value: CSV: Trailing columns JSON: Named values that don't match any column names Google Cloud Bigtable: This setting is ignored. Google Cloud Datastore backups: This setting is ignored. Avro: This setting is ignored. ORC: This setting is ignored. Parquet: This setting is ignored.",
    )
    jsonExtension: Optional[JsonExtension] = Field(
        None,
        description="Optional. Load option to be used together with source_format newline-delimited JSON to indicate that a variant of JSON is being loaded. To load newline-delimited GeoJSON, specify GEOJSON (and source_format must be set to NEWLINE_DELIMITED_JSON).",
    )
    jsonOptions: Optional[JsonOptions] = Field(
        None,
        description="Optional. Additional properties to set if sourceFormat is set to JSON.",
    )
    maxBadRecords: Optional[int] = Field(
        None,
        description="Optional. The maximum number of bad records that BigQuery can ignore when reading data. If the number of bad records exceeds this value, an invalid error is returned in the job result. The default value is 0, which requires that all records are valid. This setting is ignored for Google Cloud Bigtable, Google Cloud Datastore backups, Avro, ORC and Parquet formats.",
    )
    metadataCacheMode: Optional[MetadataCacheMode] = Field(
        None,
        description="Optional. Metadata Cache Mode for the table. Set this to enable caching of metadata from external data source.",
    )
    objectMetadata: Optional[ObjectMetadata] = Field(
        None,
        description="Optional. ObjectMetadata is used to create Object Tables. Object Tables contain a listing of objects (with their metadata) found at the source_uris. If ObjectMetadata is set, source_format should be omitted. Currently SIMPLE is the only supported Object Metadata type.",
    )
    parquetOptions: Optional[ParquetOptions] = Field(
        None,
        description="Optional. Additional properties to set if sourceFormat is set to PARQUET.",
    )
    referenceFileSchemaUri: Optional[str] = Field(
        None,
        description="Optional. When creating an external table, the user can provide a reference file with the table schema. This is enabled for the following formats: AVRO, PARQUET, ORC.",
    )
    schema_: Optional[TableSchema] = Field(
        None,
        alias="schema",
        description="Optional. The schema for the data. Schema is required for CSV and JSON formats if autodetect is not on. Schema is disallowed for Google Cloud Bigtable, Cloud Datastore backups, Avro, ORC and Parquet formats.",
    )
    sourceFormat: Optional[str] = Field(
        None,
        description='[Required] The data format. For CSV files, specify "CSV". For Google sheets, specify "GOOGLE_SHEETS". For newline-delimited JSON, specify "NEWLINE_DELIMITED_JSON". For Avro files, specify "AVRO". For Google Cloud Datastore backups, specify "DATASTORE_BACKUP". For Apache Iceberg tables, specify "ICEBERG". For ORC files, specify "ORC". For Parquet files, specify "PARQUET". [Beta] For Google Cloud Bigtable, specify "BIGTABLE".',
    )
    sourceUris: Optional[List[str]] = Field(
        None,
        description="[Required] The fully-qualified URIs that point to your data in Google Cloud. For Google Cloud Storage URIs: Each URI can contain one '*' wildcard character and it must come after the 'bucket' name. Size limits related to load jobs apply to external data sources. For Google Cloud Bigtable URIs: Exactly one URI can be specified and it has be a fully specified and valid HTTPS URL for a Google Cloud Bigtable table. For Google Cloud Datastore backups, exactly one URI can be specified. Also, the '*' wildcard character is not allowed.",
    )
    timeFormat: Optional[str] = Field(
        None,
        description="Optional. Format used to parse TIME values. Supports C-style and SQL-style values.",
    )
    timeZone: Optional[str] = Field(
        None,
        description="Optional. Time zone used when parsing timestamp values that do not have specific time zone information (e.g. 2024-04-20 12:34:56). The expected format is a IANA timezone string (e.g. America/Los_Angeles).",
    )
    timestampFormat: Optional[str] = Field(
        None,
        description="Optional. Format used to parse TIMESTAMP values. Supports C-style and SQL-style values.",
    )


class FeatureValue(BaseModel):
    categoricalValue: Optional[CategoricalValue] = Field(
        None, description="The categorical feature value."
    )
    featureColumn: Optional[str] = Field(None, description="The feature column name.")
    numericalValue: Optional[float] = Field(
        None,
        description="The numerical feature value. This is the centroid value for this feature.",
    )


class GetIamPolicyRequest(BaseModel):
    options: Optional[GetPolicyOptions] = Field(
        None,
        description="OPTIONAL: A `GetPolicyOptions` object for specifying options to `GetIamPolicy`.",
    )


class GetQueryResultsResponse(BaseModel):
    cacheHit: Optional[bool] = Field(
        None, description="Whether the query result was fetched from the query cache."
    )
    errors: Optional[List[ErrorProto]] = Field(
        None,
        description="Output only. The first errors or warnings encountered during the running of the job. The final message includes the number of errors that caused the process to stop. Errors here do not necessarily mean that the job has completed or was unsuccessful. For more information about error messages, see [Error messages](https://cloud.google.com/bigquery/docs/error-messages).",
    )
    etag: Optional[str] = Field(None, description="A hash of this response.")
    jobComplete: Optional[bool] = Field(
        None,
        description="Whether the query has completed or not. If rows or totalRows are present, this will always be true. If this is false, totalRows will not be available.",
    )
    jobReference: Optional[JobReference] = Field(
        None,
        description="Reference to the BigQuery Job that was created to run the query. This field will be present even if the original request timed out, in which case GetQueryResults can be used to read the results once the query has completed. Since this API only returns the first page of results, subsequent pages can be fetched via the same mechanism (GetQueryResults).",
    )
    kind: Optional[str] = Field(
        "bigquery#getQueryResultsResponse",
        description="The resource type of the response.",
    )
    numDmlAffectedRows: Optional[str] = Field(
        None,
        description="Output only. The number of rows affected by a DML statement. Present only for DML statements INSERT, UPDATE or DELETE.",
    )
    pageToken: Optional[str] = Field(
        None,
        description="A token used for paging results. When this token is non-empty, it indicates additional results are available.",
    )
    rows: Optional[List[TableRow]] = Field(
        None,
        description="An object with as many results as can be contained within the maximum permitted reply size. To get any additional rows, you can call GetQueryResults and specify the jobReference returned above. Present only when the query completes successfully. The REST-based representation of this data leverages a series of JSON f,v objects for indicating fields and values.",
    )
    schema_: Optional[TableSchema] = Field(
        None,
        alias="schema",
        description="The schema of the results. Present only when the query completes successfully.",
    )
    totalBytesProcessed: Optional[str] = Field(
        None, description="The total number of bytes processed for this query."
    )
    totalRows: Optional[str] = Field(
        None,
        description="The total number of rows in the complete query result set, which can be more than the number of rows in this single page of results. Present only when the query completes successfully.",
    )


class IndexUnusedReason(BaseModel):
    baseTable: Optional[TableReference] = Field(
        None,
        description="Specifies the base table involved in the reason that no search index was used.",
    )
    code: Optional[Code1] = Field(
        None,
        description="Specifies the high-level reason for the scenario when no search index was used.",
    )
    indexName: Optional[str] = Field(
        None, description="Specifies the name of the unused search index, if available."
    )
    message: Optional[str] = Field(
        None,
        description="Free form human-readable reason for the scenario when no search index was used.",
    )


class IntHparamSearchSpace(BaseModel):
    candidates: Optional[IntCandidates] = Field(
        None, description="Candidates of the int hyperparameter."
    )
    range: Optional[IntRange] = Field(
        None, description="Range of the int hyperparameter."
    )


class IterationResult(BaseModel):
    arimaResult: Optional[ArimaResult] = Field(None, description="Arima result.")
    clusterInfos: Optional[List[ClusterInfo]] = Field(
        None, description="Information about top clusters for clustering models."
    )
    durationMs: Optional[str] = Field(
        None, description="Time taken to run the iteration in milliseconds."
    )
    evalLoss: Optional[float] = Field(
        None, description="Loss computed on the eval data at the end of iteration."
    )
    index: Optional[int] = Field(None, description="Index of the iteration, 0 based.")
    learnRate: Optional[float] = Field(
        None, description="Learn rate used for this iteration."
    )
    principalComponentInfos: Optional[List[PrincipalComponentInfo]] = Field(
        None, description="The information of the principal components."
    )
    trainingLoss: Optional[float] = Field(
        None, description="Loss computed on the training data at the end of iteration."
    )


class JobConfigurationExtract(BaseModel):
    compression: Optional[str] = Field(
        None,
        description="Optional. The compression type to use for exported files. Possible values include DEFLATE, GZIP, NONE, SNAPPY, and ZSTD. The default value is NONE. Not all compression formats are support for all file formats. DEFLATE is only supported for Avro. ZSTD is only supported for Parquet. Not applicable when extracting models.",
    )
    destinationFormat: Optional[str] = Field(
        None,
        description="Optional. The exported file format. Possible values include CSV, NEWLINE_DELIMITED_JSON, PARQUET, or AVRO for tables and ML_TF_SAVED_MODEL or ML_XGBOOST_BOOSTER for models. The default value for tables is CSV. Tables with nested or repeated fields cannot be exported as CSV. The default value for models is ML_TF_SAVED_MODEL.",
    )
    destinationUri: Optional[str] = Field(
        None,
        description="[Pick one] DEPRECATED: Use destinationUris instead, passing only one URI as necessary. The fully-qualified Google Cloud Storage URI where the extracted table should be written.",
    )
    destinationUris: Optional[List[str]] = Field(
        None,
        description="[Pick one] A list of fully-qualified Google Cloud Storage URIs where the extracted table should be written.",
    )
    fieldDelimiter: Optional[str] = Field(
        None,
        description="Optional. When extracting data in CSV format, this defines the delimiter to use between fields in the exported data. Default is ','. Not applicable when extracting models.",
    )
    modelExtractOptions: Optional[ModelExtractOptions] = Field(
        None,
        description="Optional. Model extract options only applicable when extracting models.",
    )
    printHeader: Optional[bool] = Field(
        True,
        description="Optional. Whether to print out a header row in the results. Default is true. Not applicable when extracting models.",
    )
    sourceModel: Optional[ModelReference] = Field(
        None, description="A reference to the model being exported."
    )
    sourceTable: Optional[TableReference] = Field(
        None, description="A reference to the table being exported."
    )
    useAvroLogicalTypes: Optional[bool] = Field(
        None,
        description="Whether to use logical types when extracting to AVRO format. Not applicable when extracting models.",
    )


class JobConfigurationLoad(BaseModel):
    allowJaggedRows: Optional[bool] = Field(
        None,
        description="Optional. Accept rows that are missing trailing optional columns. The missing values are treated as nulls. If false, records with missing trailing columns are treated as bad records, and if there are too many bad records, an invalid error is returned in the job result. The default value is false. Only applicable to CSV, ignored for other formats.",
    )
    allowQuotedNewlines: Optional[bool] = Field(
        None,
        description="Indicates if BigQuery should allow quoted data sections that contain newline characters in a CSV file. The default value is false.",
    )
    autodetect: Optional[bool] = Field(
        None,
        description="Optional. Indicates if we should automatically infer the options and schema for CSV and JSON sources.",
    )
    clustering: Optional[Clustering] = Field(
        None, description="Clustering specification for the destination table."
    )
    columnNameCharacterMap: Optional[ColumnNameCharacterMap] = Field(
        None,
        description="Optional. Character map supported for column names in CSV/Parquet loads. Defaults to STRICT and can be overridden by Project Config Service. Using this option with unsupporting load formats will result in an error.",
    )
    connectionProperties: Optional[List[ConnectionProperty]] = Field(
        None,
        description="Optional. Connection properties which can modify the load job behavior. Currently, only the 'session_id' connection property is supported, and is used to resolve _SESSION appearing as the dataset id.",
    )
    copyFilesOnly: Optional[bool] = Field(
        None,
        description="Optional. [Experimental] Configures the load job to copy files directly to the destination BigLake managed table, bypassing file content reading and rewriting. Copying files only is supported when all the following are true: * `source_uris` are located in the same Cloud Storage location as the destination table's `storage_uri` location. * `source_format` is `PARQUET`. * `destination_table` is an existing BigLake managed table. The table's schema does not have flexible column names. The table's columns do not have type parameters other than precision and scale. * No options other than the above are specified.",
    )
    createDisposition: Optional[str] = Field(
        None,
        description="Optional. Specifies whether the job is allowed to create new tables. The following values are supported: * CREATE_IF_NEEDED: If the table does not exist, BigQuery creates the table. * CREATE_NEVER: The table must already exist. If it does not, a 'notFound' error is returned in the job result. The default value is CREATE_IF_NEEDED. Creation, truncation and append actions occur as one atomic update upon job completion.",
    )
    createSession: Optional[bool] = Field(
        None,
        description="Optional. If this property is true, the job creates a new session using a randomly generated session_id. To continue using a created session with subsequent queries, pass the existing session identifier as a `ConnectionProperty` value. The session identifier is returned as part of the `SessionInfo` message within the query statistics. The new session's location will be set to `Job.JobReference.location` if it is present, otherwise it's set to the default location based on existing routing logic.",
    )
    dateFormat: Optional[str] = Field(
        None, description="Optional. Date format used for parsing DATE values."
    )
    datetimeFormat: Optional[str] = Field(
        None, description="Optional. Date format used for parsing DATETIME values."
    )
    decimalTargetTypes: Optional[List[DecimalTargetType]] = Field(
        None,
        description='Defines the list of possible SQL data types to which the source decimal values are converted. This list and the precision and the scale parameters of the decimal field determine the target type. In the order of NUMERIC, BIGNUMERIC, and STRING, a type is picked if it is in the specified list and if it supports the precision and the scale. STRING supports all precision and scale values. If none of the listed types supports the precision and the scale, the type supporting the widest range in the specified list is picked, and if a value exceeds the supported range when reading the data, an error will be thrown. Example: Suppose the value of this field is ["NUMERIC", "BIGNUMERIC"]. If (precision,scale) is: * (38,9) -> NUMERIC; * (39,9) -> BIGNUMERIC (NUMERIC cannot hold 30 integer digits); * (38,10) -> BIGNUMERIC (NUMERIC cannot hold 10 fractional digits); * (76,38) -> BIGNUMERIC; * (77,38) -> BIGNUMERIC (error if value exceeds supported range). This field cannot contain duplicate types. The order of the types in this field is ignored. For example, ["BIGNUMERIC", "NUMERIC"] is the same as ["NUMERIC", "BIGNUMERIC"] and NUMERIC always takes precedence over BIGNUMERIC. Defaults to ["NUMERIC", "STRING"] for ORC and ["NUMERIC"] for the other file formats.',
    )
    destinationEncryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None, description="Custom encryption configuration (e.g., Cloud KMS keys)"
    )
    destinationTable: Optional[TableReference] = Field(
        None, description="[Required] The destination table to load the data into."
    )
    destinationTableProperties: Optional[DestinationTableProperties] = Field(
        None,
        description="Optional. [Experimental] Properties with which to create the destination table if it is new.",
    )
    encoding: Optional[str] = Field(
        None,
        description="Optional. The character encoding of the data. The supported values are UTF-8, ISO-8859-1, UTF-16BE, UTF-16LE, UTF-32BE, and UTF-32LE. The default value is UTF-8. BigQuery decodes the data after the raw, binary data has been split using the values of the `quote` and `fieldDelimiter` properties. If you don't specify an encoding, or if you specify a UTF-8 encoding when the CSV file is not UTF-8 encoded, BigQuery attempts to convert the data to UTF-8. Generally, your data loads successfully, but it may not match byte-for-byte what you expect. To avoid this, specify the correct encoding by using the `--encoding` flag. If BigQuery can't convert a character other than the ASCII `0` character, BigQuery converts the character to the standard Unicode replacement character: �.",
    )
    fieldDelimiter: Optional[str] = Field(
        None,
        description='Optional. The separator character for fields in a CSV file. The separator is interpreted as a single byte. For files encoded in ISO-8859-1, any single character can be used as a separator. For files encoded in UTF-8, characters represented in decimal range 1-127 (U+0001-U+007F) can be used without any modification. UTF-8 characters encoded with multiple bytes (i.e. U+0080 and above) will have only the first byte used for separating fields. The remaining bytes will be treated as a part of the field. BigQuery also supports the escape sequence "\\t" (U+0009) to specify a tab separator. The default value is comma (",", U+002C).',
    )
    fileSetSpecType: Optional[FileSetSpecType] = Field(
        None,
        description="Optional. Specifies how source URIs are interpreted for constructing the file set to load. By default, source URIs are expanded against the underlying storage. You can also specify manifest files to control how the file set is constructed. This option is only applicable to object storage systems.",
    )
    hivePartitioningOptions: Optional[HivePartitioningOptions] = Field(
        None,
        description="Optional. When set, configures hive partitioning support. Not all storage formats support hive partitioning -- requesting hive partitioning on an unsupported format will lead to an error, as will providing an invalid specification.",
    )
    ignoreUnknownValues: Optional[bool] = Field(
        None,
        description="Optional. Indicates if BigQuery should allow extra values that are not represented in the table schema. If true, the extra values are ignored. If false, records with extra columns are treated as bad records, and if there are too many bad records, an invalid error is returned in the job result. The default value is false. The sourceFormat property determines what BigQuery treats as an extra value: CSV: Trailing columns JSON: Named values that don't match any column names in the table schema Avro, Parquet, ORC: Fields in the file schema that don't exist in the table schema.",
    )
    jsonExtension: Optional[JsonExtension] = Field(
        None,
        description="Optional. Load option to be used together with source_format newline-delimited JSON to indicate that a variant of JSON is being loaded. To load newline-delimited GeoJSON, specify GEOJSON (and source_format must be set to NEWLINE_DELIMITED_JSON).",
    )
    maxBadRecords: Optional[int] = Field(
        None,
        description="Optional. The maximum number of bad records that BigQuery can ignore when running the job. If the number of bad records exceeds this value, an invalid error is returned in the job result. The default value is 0, which requires that all records are valid. This is only supported for CSV and NEWLINE_DELIMITED_JSON file formats.",
    )
    nullMarker: Optional[str] = Field(
        None,
        description='Optional. Specifies a string that represents a null value in a CSV file. For example, if you specify "\\N", BigQuery interprets "\\N" as a null value when loading a CSV file. The default value is the empty string. If you set this property to a custom value, BigQuery throws an error if an empty string is present for all data types except for STRING and BYTE. For STRING and BYTE columns, BigQuery interprets the empty string as an empty value.',
    )
    nullMarkers: Optional[List[str]] = Field(
        None,
        description="Optional. A list of strings represented as SQL NULL value in a CSV file. null_marker and null_markers can't be set at the same time. If null_marker is set, null_markers has to be not set. If null_markers is set, null_marker has to be not set. If both null_marker and null_markers are set at the same time, a user error would be thrown. Any strings listed in null_markers, including empty string would be interpreted as SQL NULL. This applies to all column types.",
    )
    parquetOptions: Optional[ParquetOptions] = Field(
        None,
        description="Optional. Additional properties to set if sourceFormat is set to PARQUET.",
    )
    preserveAsciiControlCharacters: Optional[bool] = Field(
        None,
        description="Optional. When sourceFormat is set to \"CSV\", this indicates whether the embedded ASCII control characters (the first 32 characters in the ASCII-table, from '\\x00' to '\\x1F') are preserved.",
    )
    projectionFields: Optional[List[str]] = Field(
        None,
        description='If sourceFormat is set to "DATASTORE_BACKUP", indicates which entity properties to load into BigQuery from a Cloud Datastore backup. Property names are case sensitive and must be top-level properties. If no properties are specified, BigQuery loads all properties. If any named property isn\'t found in the Cloud Datastore backup, an invalid error is returned in the job result.',
    )
    quote: Optional[constr(pattern=r".?")] = Field(
        '"',
        description="Optional. The value that is used to quote data sections in a CSV file. BigQuery converts the string to ISO-8859-1 encoding, and then uses the first byte of the encoded string to split the data in its raw, binary state. The default value is a double-quote ('\"'). If your data does not contain quoted sections, set the property value to an empty string. If your data contains quoted newline characters, you must also set the allowQuotedNewlines property to true. To include the specific quote character within a quoted value, precede it with an additional matching quote character. For example, if you want to escape the default character ' \" ', use ' \"\" '. @default \"",
    )
    rangePartitioning: Optional[RangePartitioning] = Field(
        None,
        description="Range partitioning specification for the destination table. Only one of timePartitioning and rangePartitioning should be specified.",
    )
    referenceFileSchemaUri: Optional[str] = Field(
        None,
        description="Optional. The user can provide a reference file with the reader schema. This file is only loaded if it is part of source URIs, but is not loaded otherwise. It is enabled for the following formats: AVRO, PARQUET, ORC.",
    )
    schema_: Optional[TableSchema] = Field(
        None,
        alias="schema",
        description="Optional. The schema for the destination table. The schema can be omitted if the destination table already exists, or if you're loading data from Google Cloud Datastore.",
    )
    schemaInline: Optional[str] = Field(
        None,
        description='[Deprecated] The inline schema. For CSV schemas, specify as "Field1:Type1[,Field2:Type2]*". For example, "foo:STRING, bar:INTEGER, baz:FLOAT".',
    )
    schemaInlineFormat: Optional[str] = Field(
        None, description="[Deprecated] The format of the schemaInline property."
    )
    schemaUpdateOptions: Optional[List[str]] = Field(
        None,
        description="Allows the schema of the destination table to be updated as a side effect of the load job if a schema is autodetected or supplied in the job configuration. Schema update options are supported in two cases: when writeDisposition is WRITE_APPEND; when writeDisposition is WRITE_TRUNCATE and the destination table is a partition of a table, specified by partition decorators. For normal tables, WRITE_TRUNCATE will always overwrite the schema. One or more of the following values are specified: * ALLOW_FIELD_ADDITION: allow adding a nullable field to the schema. * ALLOW_FIELD_RELAXATION: allow relaxing a required field in the original schema to nullable.",
    )
    skipLeadingRows: Optional[int] = Field(
        None,
        description="Optional. The number of rows at the top of a CSV file that BigQuery will skip when loading the data. The default value is 0. This property is useful if you have header rows in the file that should be skipped. When autodetect is on, the behavior is the following: * skipLeadingRows unspecified - Autodetect tries to detect headers in the first row. If they are not detected, the row is read as data. Otherwise data is read starting from the second row. * skipLeadingRows is 0 - Instructs autodetect that there are no headers and data should be read starting from the first row. * skipLeadingRows = N > 0 - Autodetect skips N-1 rows and tries to detect headers in row N. If headers are not detected, row N is just skipped. Otherwise row N is used to extract column names for the detected schema.",
    )
    sourceColumnMatch: Optional[SourceColumnMatch] = Field(
        None,
        description="Optional. Controls the strategy used to match loaded columns to the schema. If not set, a sensible default is chosen based on how the schema is provided. If autodetect is used, then columns are matched by name. Otherwise, columns are matched by position. This is done to keep the behavior backward-compatible.",
    )
    sourceFormat: Optional[str] = Field(
        None,
        description='Optional. The format of the data files. For CSV files, specify "CSV". For datastore backups, specify "DATASTORE_BACKUP". For newline-delimited JSON, specify "NEWLINE_DELIMITED_JSON". For Avro, specify "AVRO". For parquet, specify "PARQUET". For orc, specify "ORC". The default value is CSV.',
    )
    sourceUris: Optional[List[str]] = Field(
        None,
        description="[Required] The fully-qualified URIs that point to your data in Google Cloud. For Google Cloud Storage URIs: Each URI can contain one '*' wildcard character and it must come after the 'bucket' name. Size limits related to load jobs apply to external data sources. For Google Cloud Bigtable URIs: Exactly one URI can be specified and it has be a fully specified and valid HTTPS URL for a Google Cloud Bigtable table. For Google Cloud Datastore backups: Exactly one URI can be specified. Also, the '*' wildcard character is not allowed.",
    )
    timeFormat: Optional[str] = Field(
        None, description="Optional. Date format used for parsing TIME values."
    )
    timePartitioning: Optional[TimePartitioning] = Field(
        None,
        description="Time-based partitioning specification for the destination table. Only one of timePartitioning and rangePartitioning should be specified.",
    )
    timeZone: Optional[str] = Field(
        None,
        description="Optional. [Experimental] Default time zone that will apply when parsing timestamp values that have no specific time zone.",
    )
    timestampFormat: Optional[str] = Field(
        None, description="Optional. Date format used for parsing TIMESTAMP values."
    )
    useAvroLogicalTypes: Optional[bool] = Field(
        None,
        description='Optional. If sourceFormat is set to "AVRO", indicates whether to interpret logical types as the corresponding BigQuery data type (for example, TIMESTAMP), instead of using the raw type (for example, INTEGER).',
    )
    writeDisposition: Optional[str] = Field(
        None,
        description="Optional. Specifies the action that occurs if the destination table already exists. The following values are supported: * WRITE_TRUNCATE: If the table already exists, BigQuery overwrites the data, removes the constraints and uses the schema from the load job. * WRITE_APPEND: If the table already exists, BigQuery appends the data to the table. * WRITE_EMPTY: If the table already exists and contains data, a 'duplicate' error is returned in the job result. The default value is WRITE_APPEND. Each action is atomic and only occurs if BigQuery is able to complete the job successfully. Creation, truncation and append actions occur as one atomic update upon job completion.",
    )


class JobConfigurationTableCopy(BaseModel):
    createDisposition: Optional[str] = Field(
        None,
        description="Optional. Specifies whether the job is allowed to create new tables. The following values are supported: * CREATE_IF_NEEDED: If the table does not exist, BigQuery creates the table. * CREATE_NEVER: The table must already exist. If it does not, a 'notFound' error is returned in the job result. The default value is CREATE_IF_NEEDED. Creation, truncation and append actions occur as one atomic update upon job completion.",
    )
    destinationEncryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None, description="Custom encryption configuration (e.g., Cloud KMS keys)."
    )
    destinationExpirationTime: Optional[str] = Field(
        None,
        description="Optional. The time when the destination table expires. Expired tables will be deleted and their storage reclaimed.",
    )
    destinationTable: Optional[TableReference] = Field(
        None, description="[Required] The destination table."
    )
    operationType: Optional[OperationType] = Field(
        None, description="Optional. Supported operation types in table copy job."
    )
    sourceTable: Optional[TableReference] = Field(
        None, description="[Pick one] Source table to copy."
    )
    sourceTables: Optional[List[TableReference]] = Field(
        None, description="[Pick one] Source tables to copy."
    )
    writeDisposition: Optional[str] = Field(
        None,
        description="Optional. Specifies the action that occurs if the destination table already exists. The following values are supported: * WRITE_TRUNCATE: If the table already exists, BigQuery overwrites the table data and uses the schema and table constraints from the source table. * WRITE_APPEND: If the table already exists, BigQuery appends the data to the table. * WRITE_EMPTY: If the table already exists and contains data, a 'duplicate' error is returned in the job result. The default value is WRITE_EMPTY. Each action is atomic and only occurs if BigQuery is able to complete the job successfully. Creation, truncation and append actions occur as one atomic update upon job completion.",
    )


class JobStatistics3(BaseModel):
    badRecords: Optional[str] = Field(
        None,
        description="Output only. The number of bad records encountered. Note that if the job has failed because of more bad records encountered than the maximum allowed in the load job configuration, then this number can be less than the total number of bad records present in the input data.",
    )
    inputFileBytes: Optional[str] = Field(
        None, description="Output only. Number of bytes of source data in a load job."
    )
    inputFiles: Optional[str] = Field(
        None, description="Output only. Number of source files in a load job."
    )
    outputBytes: Optional[str] = Field(
        None,
        description="Output only. Size of the loaded data in bytes. Note that while a load job is in the running state, this value may change.",
    )
    outputRows: Optional[str] = Field(
        None,
        description="Output only. Number of rows imported in a load job. Note that while an import job is in the running state, this value may change.",
    )
    timeline: Optional[List[QueryTimelineSample]] = Field(
        None, description="Output only. Describes a timeline of job execution."
    )


class JobStatistics4(BaseModel):
    destinationUriFileCounts: Optional[List[str]] = Field(
        None,
        description="Output only. Number of files per destination URI or URI pattern specified in the extract configuration. These values will be in the same order as the URIs specified in the 'destinationUris' field.",
    )
    inputBytes: Optional[str] = Field(
        None,
        description="Output only. Number of user bytes extracted into the result. This is the byte count as computed by BigQuery for billing purposes and doesn't have any relationship with the number of actual result bytes extracted in the desired format.",
    )
    timeline: Optional[List[QueryTimelineSample]] = Field(
        None, description="Output only. Describes a timeline of job execution."
    )


class JsonObject(RootModel[Optional[Dict[str, JsonValue]]]):
    root: Optional[Dict[str, JsonValue]] = None


class MaterializedView(BaseModel):
    chosen: Optional[bool] = Field(
        None,
        description="Whether the materialized view is chosen for the query. A materialized view can be chosen to rewrite multiple parts of the same query. If a materialized view is chosen to rewrite any part of the query, then this field is true, even if the materialized view was not chosen to rewrite others parts.",
    )
    estimatedBytesSaved: Optional[str] = Field(
        None,
        description="If present, specifies a best-effort estimation of the bytes saved by using the materialized view rather than its base tables.",
    )
    rejectedReason: Optional[RejectedReason] = Field(
        None,
        description="If present, specifies the reason why the materialized view was not chosen for the query.",
    )
    tableReference: Optional[TableReference] = Field(
        None, description="The candidate materialized view."
    )


class MaterializedViewStatistics(BaseModel):
    materializedView: Optional[List[MaterializedView]] = Field(
        None,
        description="Materialized views considered for the query job. Only certain materialized views are used. For a detailed list, see the child message. If many materialized views are considered, then the list might be incomplete.",
    )


class MultiClassClassificationMetrics(BaseModel):
    aggregateClassificationMetrics: Optional[AggregateClassificationMetrics] = Field(
        None, description="Aggregate classification metrics."
    )
    confusionMatrixList: Optional[List[ConfusionMatrix]] = Field(
        None, description="Confusion matrix at different thresholds."
    )


class PartitionSkew(BaseModel):
    skewSources: Optional[List[SkewSource]] = Field(
        None, description="Output only. Source stages which produce skewed data."
    )


class Policy(BaseModel):
    auditConfigs: Optional[List[AuditConfig]] = Field(
        None, description="Specifies cloud audit logging configuration for this policy."
    )
    bindings: Optional[List[Binding]] = Field(
        None,
        description="Associates a list of `members`, or principals, with a `role`. Optionally, may specify a `condition` that determines how and when the `bindings` are applied. Each of the `bindings` must contain at least one principal. The `bindings` in a `Policy` can refer to up to 1,500 principals; up to 250 of these principals can be Google groups. Each occurrence of a principal counts towards these limits. For example, if the `bindings` grant 50 different roles to `user:alice@example.com`, and not to any other principal, then you can add another 1,450 principals to the `bindings` in the `Policy`.",
    )
    etag: Optional[str] = Field(
        None,
        description="`etag` is used for optimistic concurrency control as a way to help prevent simultaneous updates of a policy from overwriting each other. It is strongly suggested that systems make use of the `etag` in the read-modify-write cycle to perform policy updates in order to avoid race conditions: An `etag` is returned in the response to `getIamPolicy`, and systems are expected to put that etag in the request to `setIamPolicy` to ensure that their change will be applied to the same version of the policy. **Important:** If you use IAM Conditions, you must include the `etag` field whenever you call `setIamPolicy`. If you omit this field, then IAM allows you to overwrite a version `3` policy with a version `1` policy, and all of the conditions in the version `3` policy are lost.",
    )
    version: Optional[int] = Field(
        None,
        description="Specifies the format of the policy. Valid values are `0`, `1`, and `3`. Requests that specify an invalid value are rejected. Any operation that affects conditional role bindings must specify version `3`. This requirement applies to the following operations: * Getting a policy that includes a conditional role binding * Adding a conditional role binding to a policy * Changing a conditional role binding in a policy * Removing any role binding, with or without a condition, from a policy that includes conditions **Important:** If you use IAM Conditions, you must include the `etag` field whenever you call `setIamPolicy`. If you omit this field, then IAM allows you to overwrite a version `3` policy with a version `1` policy, and all of the conditions in the version `3` policy are lost. If a policy does not include any conditions, operations on that policy may specify any valid version or leave the field unset. To learn which resources support conditions in their IAM policies, see the [IAM documentation](https://cloud.google.com/iam/help/conditions/resource-policies).",
    )


class Project(BaseModel):
    friendlyName: Optional[str] = Field(
        None,
        description="A descriptive name for this project. A wrapper is used here because friendlyName can be set to the empty string.",
    )
    id: Optional[str] = Field(None, description="An opaque ID of this project.")
    kind: Optional[str] = Field(None, description="The resource type.")
    numericId: Optional[str] = Field(
        None, description="The numeric ID of this project."
    )
    projectReference: Optional[ProjectReference] = Field(
        None, description="A unique reference to this project."
    )


class ProjectList(BaseModel):
    etag: Optional[str] = Field(None, description="A hash of the page of results.")
    kind: Optional[str] = Field(
        "bigquery#projectList", description="The resource type of the response."
    )
    nextPageToken: Optional[str] = Field(
        None, description="Use this token to request the next page of results."
    )
    projects: Optional[List[Project]] = Field(
        None, description="Projects to which the user has at least READ access."
    )
    totalItems: Optional[int] = Field(
        None,
        description="The total number of projects in the page. A wrapper is used here because the field should still be in the response when the value is 0.",
    )


class QueryResponse(BaseModel):
    cacheHit: Optional[bool] = Field(
        None, description="Whether the query result was fetched from the query cache."
    )
    creationTime: Optional[str] = Field(
        None,
        description="Output only. Creation time of this query, in milliseconds since the epoch. This field will be present on all queries.",
    )
    dmlStats: Optional[DmlStatistics] = Field(
        None,
        description="Output only. Detailed statistics for DML statements INSERT, UPDATE, DELETE, MERGE or TRUNCATE.",
    )
    endTime: Optional[str] = Field(
        None,
        description="Output only. End time of this query, in milliseconds since the epoch. This field will be present whenever a query job is in the DONE state.",
    )
    errors: Optional[List[ErrorProto]] = Field(
        None,
        description="Output only. The first errors or warnings encountered during the running of the job. The final message includes the number of errors that caused the process to stop. Errors here do not necessarily mean that the job has completed or was unsuccessful. For more information about error messages, see [Error messages](https://cloud.google.com/bigquery/docs/error-messages).",
    )
    jobComplete: Optional[bool] = Field(
        None,
        description="Whether the query has completed or not. If rows or totalRows are present, this will always be true. If this is false, totalRows will not be available.",
    )
    jobCreationReason: Optional[JobCreationReason] = Field(
        None,
        description="Optional. The reason why a Job was created. Only relevant when a job_reference is present in the response. If job_reference is not present it will always be unset. [Preview](https://cloud.google.com/products/#product-launch-stages)",
    )
    jobReference: Optional[JobReference] = Field(
        None,
        description="Reference to the Job that was created to run the query. This field will be present even if the original request timed out, in which case GetQueryResults can be used to read the results once the query has completed. Since this API only returns the first page of results, subsequent pages can be fetched via the same mechanism (GetQueryResults). If job_creation_mode was set to `JOB_CREATION_OPTIONAL` and the query completes without creating a job, this field will be empty.",
    )
    kind: Optional[str] = Field(
        "bigquery#queryResponse", description="The resource type."
    )
    location: Optional[str] = Field(
        None,
        description="Output only. The geographic location of the query. For more information about BigQuery locations, see: https://cloud.google.com/bigquery/docs/locations",
    )
    numDmlAffectedRows: Optional[str] = Field(
        None,
        description="Output only. The number of rows affected by a DML statement. Present only for DML statements INSERT, UPDATE or DELETE.",
    )
    pageToken: Optional[str] = Field(
        None,
        description="A token used for paging results. A non-empty token indicates that additional results are available. To see additional results, query the [`jobs.getQueryResults`](https://cloud.google.com/bigquery/docs/reference/rest/v2/jobs/getQueryResults) method. For more information, see [Paging through table data](https://cloud.google.com/bigquery/docs/paging-results).",
    )
    queryId: Optional[str] = Field(
        None,
        description="Auto-generated ID for the query. [Preview](https://cloud.google.com/products/#product-launch-stages)",
    )
    rows: Optional[List[TableRow]] = Field(
        None,
        description="An object with as many results as can be contained within the maximum permitted reply size. To get any additional rows, you can call GetQueryResults and specify the jobReference returned above.",
    )
    schema_: Optional[TableSchema] = Field(
        None,
        alias="schema",
        description="The schema of the results. Present only when the query completes successfully.",
    )
    sessionInfo: Optional[SessionInfo] = Field(
        None,
        description="Output only. Information of the session if this job is part of one.",
    )
    startTime: Optional[str] = Field(
        None,
        description="Output only. Start time of this query, in milliseconds since the epoch. This field will be present when the query job transitions from the PENDING state to either RUNNING or DONE.",
    )
    totalBytesBilled: Optional[str] = Field(
        None,
        description="Output only. If the project is configured to use on-demand pricing, then this field contains the total bytes billed for the job. If the project is configured to use flat-rate pricing, then you are not billed for bytes and this field is informational only.",
    )
    totalBytesProcessed: Optional[str] = Field(
        None,
        description="The total number of bytes processed for this query. If this query was a dry run, this is the number of bytes that would be processed if the query were run.",
    )
    totalRows: Optional[str] = Field(
        None,
        description="The total number of rows in the complete query result set, which can be more than the number of rows in this single page of results.",
    )
    totalSlotMs: Optional[str] = Field(
        None,
        description="Output only. Number of slot ms the user is actually billed for.",
    )


class RowAccessPolicy(BaseModel):
    creationTime: Optional[str] = Field(
        None,
        description="Output only. The time when this row access policy was created, in milliseconds since the epoch.",
    )
    etag: Optional[str] = Field(
        None, description="Output only. A hash of this resource."
    )
    filterPredicate: Optional[str] = Field(
        None,
        description="Required. A SQL boolean expression that represents the rows defined by this row access policy, similar to the boolean expression in a WHERE clause of a SELECT query on a table. References to other tables, routines, and temporary functions are not supported. Examples: region=\"EU\" date_field = CAST('2019-9-27' as DATE) nullable_field is not NULL numeric_field BETWEEN 1.0 AND 5.0",
    )
    grantees: Optional[List[str]] = Field(
        None,
        description='Optional. Input only. The optional list of iam_member users or groups that specifies the initial members that the row-level access policy should be created with. grantees types: - "user:alice@example.com": An email address that represents a specific Google account. - "serviceAccount:my-other-app@appspot.gserviceaccount.com": An email address that represents a service account. - "group:admins@example.com": An email address that represents a Google group. - "domain:example.com":The Google Workspace domain (primary) that represents all the users of that domain. - "allAuthenticatedUsers": A special identifier that represents all service accounts and all users on the internet who have authenticated with a Google Account. This identifier includes accounts that aren\'t connected to a Google Workspace or Cloud Identity domain, such as personal Gmail accounts. Users who aren\'t authenticated, such as anonymous visitors, aren\'t included. - "allUsers":A special identifier that represents anyone who is on the internet, including authenticated and unauthenticated users. Because BigQuery requires authentication before a user can access the service, allUsers includes only authenticated users.',
    )
    lastModifiedTime: Optional[str] = Field(
        None,
        description="Output only. The time when this row access policy was last modified, in milliseconds since the epoch.",
    )
    rowAccessPolicyReference: Optional[RowAccessPolicyReference] = Field(
        None,
        description="Required. Reference describing the ID of this row access policy.",
    )


class SearchStatistics(BaseModel):
    indexUnusedReasons: Optional[List[IndexUnusedReason]] = Field(
        None,
        description="When `indexUsageMode` is `UNUSED` or `PARTIALLY_USED`, this field explains why indexes were not used in all or part of the search query. If `indexUsageMode` is `FULLY_USED`, this field is not populated.",
    )
    indexUsageMode: Optional[IndexUsageMode] = Field(
        None, description="Specifies the index usage mode for the query."
    )


class SetIamPolicyRequest(BaseModel):
    policy: Optional[Policy] = Field(
        None,
        description="REQUIRED: The complete policy to be applied to the `resource`. The size of the policy is limited to a few 10s of KB. An empty policy is a valid policy but certain Google Cloud services (such as Projects) might reject them.",
    )
    updateMask: Optional[str] = Field(
        None,
        description='OPTIONAL: A FieldMask specifying which fields of the policy to modify. Only the fields in the mask will be modified. If no mask is provided, the following default mask is used: `paths: "bindings, etag"`',
    )


class SnapshotDefinition(BaseModel):
    baseTableReference: Optional[TableReference] = Field(
        None,
        description="Required. Reference describing the ID of the table that was snapshot.",
    )
    snapshotTime: Optional[AwareDatetime] = Field(
        None,
        description="Required. The time at which the base table was snapshot. This value is reported in the JSON response using RFC3339 format.",
    )


class StagePerformanceStandaloneInsight(BaseModel):
    biEngineReasons: Optional[List[BiEngineReason]] = Field(
        None,
        description="Output only. If present, the stage had the following reasons for being disqualified from BI Engine execution.",
    )
    highCardinalityJoins: Optional[List[HighCardinalityJoin]] = Field(
        None, description="Output only. High cardinality joins in the stage."
    )
    insufficientShuffleQuota: Optional[bool] = Field(
        None,
        description="Output only. True if the stage has insufficient shuffle quota.",
    )
    partitionSkew: Optional[PartitionSkew] = Field(
        None, description="Output only. Partition skew in the stage."
    )
    slotContention: Optional[bool] = Field(
        None, description="Output only. True if the stage has a slot contention issue."
    )
    stageId: Optional[str] = Field(
        None, description="Output only. The stage id that the insight mapped to."
    )


class StoredColumnsUsage(BaseModel):
    baseTable: Optional[TableReference] = Field(
        None, description="Specifies the base table."
    )
    isQueryAccelerated: Optional[bool] = Field(
        None,
        description="Specifies whether the query was accelerated with stored columns.",
    )
    storedColumnsUnusedReasons: Optional[List[StoredColumnsUnusedReason]] = Field(
        None, description="If stored columns were not used, explain why."
    )


class Table(BaseModel):
    biglakeConfiguration: Optional[BigLakeConfiguration] = Field(
        None,
        description="Optional. Specifies the configuration of a BigLake managed table.",
    )
    cloneDefinition: Optional[CloneDefinition] = Field(
        None,
        description="Output only. Contains information about the clone. This value is set via the clone operation.",
    )
    clustering: Optional[Clustering] = Field(
        None,
        description="Clustering specification for the table. Must be specified with time-based partitioning, data in the table will be first partitioned and subsequently clustered.",
    )
    creationTime: Optional[str] = Field(
        None,
        description="Output only. The time when this table was created, in milliseconds since the epoch.",
    )
    defaultCollation: Optional[str] = Field(
        None,
        description="Optional. Defines the default collation specification of new STRING fields in the table. During table creation or update, if a STRING field is added to this table without explicit collation specified, then the table inherits the table default collation. A change to this field affects only fields added afterwards, and does not alter the existing fields. The following values are supported: * 'und:ci': undetermined locale, case insensitive. * '': empty string. Default to case-sensitive behavior.",
    )
    defaultRoundingMode: Optional[DefaultRoundingMode] = Field(
        None,
        description="Optional. Defines the default rounding mode specification of new decimal fields (NUMERIC OR BIGNUMERIC) in the table. During table creation or update, if a decimal field is added to this table without an explicit rounding mode specified, then the field inherits the table default rounding mode. Changing this field doesn't affect existing fields.",
    )
    description: Optional[str] = Field(
        None, description="Optional. A user-friendly description of this table."
    )
    encryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None, description="Custom encryption configuration (e.g., Cloud KMS keys)."
    )
    etag: Optional[str] = Field(
        None, description="Output only. A hash of this resource."
    )
    expirationTime: Optional[str] = Field(
        None,
        description="Optional. The time when this table expires, in milliseconds since the epoch. If not present, the table will persist indefinitely. Expired tables will be deleted and their storage reclaimed. The defaultTableExpirationMs property of the encapsulating dataset can be used to set a default expirationTime on newly created tables.",
    )
    externalCatalogTableOptions: Optional[ExternalCatalogTableOptions] = Field(
        None, description="Optional. Options defining open source compatible table."
    )
    externalDataConfiguration: Optional[ExternalDataConfiguration] = Field(
        None,
        description="Optional. Describes the data format, location, and other properties of a table stored outside of BigQuery. By defining these properties, the data source can then be queried as if it were a standard BigQuery table.",
    )
    friendlyName: Optional[str] = Field(
        None, description="Optional. A descriptive name for this table."
    )
    id: Optional[str] = Field(
        None, description="Output only. An opaque ID uniquely identifying the table."
    )
    kind: Optional[str] = Field(
        "bigquery#table", description="The type of resource ID."
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="The labels associated with this table. You can use these to organize and group your tables. Label keys and values can be no longer than 63 characters, can only contain lowercase letters, numeric characters, underscores and dashes. International characters are allowed. Label values are optional. Label keys must start with a letter and each label in the list must have a different key.",
    )
    lastModifiedTime: Optional[str] = Field(
        None,
        description="Output only. The time when this table was last modified, in milliseconds since the epoch.",
    )
    location: Optional[str] = Field(
        None,
        description="Output only. The geographic location where the table resides. This value is inherited from the dataset.",
    )
    managedTableType: Optional[ManagedTableType] = Field(
        None,
        description="Optional. If set, overrides the default managed table type configured in the dataset.",
    )
    materializedView: Optional[MaterializedViewDefinition] = Field(
        None, description="Optional. The materialized view definition."
    )
    materializedViewStatus: Optional[MaterializedViewStatus] = Field(
        None, description="Output only. The materialized view status."
    )
    maxStaleness: Optional[str] = Field(
        None,
        description="Optional. The maximum staleness of data that could be returned when the table (or stale MV) is queried. Staleness encoded as a string encoding of sql IntervalValue type.",
    )
    model: Optional[ModelDefinition] = Field(None, description="Deprecated.")
    numActiveLogicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of logical bytes that are less than 90 days old.",
    )
    numActivePhysicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of physical bytes less than 90 days old. This data is not kept in real time, and might be delayed by a few seconds to a few minutes.",
    )
    numBytes: Optional[str] = Field(
        None,
        description="Output only. The size of this table in logical bytes, excluding any data in the streaming buffer.",
    )
    numCurrentPhysicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of physical bytes used by current live data storage. This data is not kept in real time, and might be delayed by a few seconds to a few minutes.",
    )
    numLongTermBytes: Optional[str] = Field(
        None,
        description='Output only. The number of logical bytes in the table that are considered "long-term storage".',
    )
    numLongTermLogicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of logical bytes that are more than 90 days old.",
    )
    numLongTermPhysicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of physical bytes more than 90 days old. This data is not kept in real time, and might be delayed by a few seconds to a few minutes.",
    )
    numPartitions: Optional[str] = Field(
        None,
        description="Output only. The number of partitions present in the table or materialized view. This data is not kept in real time, and might be delayed by a few seconds to a few minutes.",
    )
    numPhysicalBytes: Optional[str] = Field(
        None,
        description="Output only. The physical size of this table in bytes. This includes storage used for time travel.",
    )
    numRows: Optional[str] = Field(
        None,
        description="Output only. The number of rows of data in this table, excluding any data in the streaming buffer.",
    )
    numTimeTravelPhysicalBytes: Optional[str] = Field(
        None,
        description="Output only. Number of physical bytes used by time travel storage (deleted or changed data). This data is not kept in real time, and might be delayed by a few seconds to a few minutes.",
    )
    numTotalLogicalBytes: Optional[str] = Field(
        None,
        description="Output only. Total number of logical bytes in the table or materialized view.",
    )
    numTotalPhysicalBytes: Optional[str] = Field(
        None,
        description="Output only. The physical size of this table in bytes. This also includes storage used for time travel. This data is not kept in real time, and might be delayed by a few seconds to a few minutes.",
    )
    partitionDefinition: Optional[PartitioningDefinition] = Field(
        None,
        description="Optional. The partition information for all table formats, including managed partitioned tables, hive partitioned tables, iceberg partitioned, and metastore partitioned tables. This field is only populated for metastore partitioned tables. For other table formats, this is an output only field.",
    )
    rangePartitioning: Optional[RangePartitioning] = Field(
        None, description="If specified, configures range partitioning for this table."
    )
    replicas: Optional[List[TableReference]] = Field(
        None,
        description="Optional. Output only. Table references of all replicas currently active on the table.",
    )
    requirePartitionFilter: Optional[bool] = Field(
        False,
        description="Optional. If set to true, queries over this table require a partition filter that can be used for partition elimination to be specified.",
    )
    resourceTags: Optional[Dict[str, str]] = Field(
        None,
        description='[Optional] The tags associated with this table. Tag keys are globally unique. See additional information on [tags](https://cloud.google.com/iam/docs/tags-access-control#definitions). An object containing a list of "key": value pairs. The key is the namespaced friendly name of the tag key, e.g. "12345/environment" where 12345 is parent id. The value is the friendly short name of the tag value, e.g. "production".',
    )
    restrictions: Optional[RestrictionConfig] = Field(
        None,
        description="Optional. Output only. Restriction config for table. If set, restrict certain accesses on the table based on the config. See [Data egress](https://cloud.google.com/bigquery/docs/analytics-hub-introduction#data_egress) for more details.",
    )
    schema_: Optional[TableSchema] = Field(
        None,
        alias="schema",
        description="Optional. Describes the schema of this table.",
    )
    selfLink: Optional[str] = Field(
        None,
        description="Output only. A URL that can be used to access this resource again.",
    )
    snapshotDefinition: Optional[SnapshotDefinition] = Field(
        None,
        description="Output only. Contains information about the snapshot. This value is set via snapshot creation.",
    )
    streamingBuffer: Optional[Streamingbuffer] = Field(
        None,
        description="Output only. Contains information regarding this table's streaming buffer, if one is present. This field will be absent if the table is not being streamed to or if there is no data in the streaming buffer.",
    )
    tableConstraints: Optional[TableConstraints] = Field(
        None, description="Optional. Tables Primary Key and Foreign Key information"
    )
    tableReference: Optional[TableReference] = Field(
        None, description="Required. Reference describing the ID of this table."
    )
    tableReplicationInfo: Optional[TableReplicationInfo] = Field(
        None,
        description="Optional. Table replication info for table created `AS REPLICA` DDL like: `CREATE MATERIALIZED VIEW mv1 AS REPLICA OF src_mv`",
    )
    timePartitioning: Optional[TimePartitioning] = Field(
        None,
        description="If specified, configures time-based partitioning for this table.",
    )
    type: Optional[str] = Field(
        None,
        description="Output only. Describes the table type. The following values are supported: * `TABLE`: A normal BigQuery table. * `VIEW`: A virtual table defined by a SQL query. * `EXTERNAL`: A table that references data stored in an external storage system, such as Google Cloud Storage. * `MATERIALIZED_VIEW`: A precomputed view defined by a SQL query. * `SNAPSHOT`: An immutable BigQuery table that preserves the contents of a base table at a particular time. See additional information on [table snapshots](https://cloud.google.com/bigquery/docs/table-snapshots-intro). The default value is `TABLE`.",
    )
    view: Optional[ViewDefinition] = Field(
        None, description="Optional. The view definition."
    )


class Row1(BaseModel):
    insertId: Optional[str] = Field(
        None,
        description="Insertion ID for best-effort deduplication. This feature is not recommended, and users seeking stronger insertion semantics are encouraged to use other mechanisms such as the BigQuery Write API.",
    )
    json_: Optional[JsonObject] = Field(
        None, alias="json", description="Data for a single row."
    )


class TableDataInsertAllRequest(BaseModel):
    ignoreUnknownValues: Optional[bool] = Field(
        None,
        description="Optional. Accept rows that contain values that do not match the schema. The unknown values are ignored. Default is false, which treats unknown values as errors.",
    )
    kind: Optional[str] = Field(
        "bigquery#tableDataInsertAllRequest",
        description='Optional. The resource type of the response. The value is not checked at the backend. Historically, it has been set to "bigquery#tableDataInsertAllRequest" but you are not required to set it.',
    )
    rows: Optional[List[Row1]] = None
    skipInvalidRows: Optional[bool] = Field(
        None,
        description="Optional. Insert all valid rows of a request, even if invalid rows exist. The default value is false, which causes the entire request to fail if any invalid rows exist.",
    )
    templateSuffix: Optional[str] = Field(
        None,
        description='Optional. If specified, treats the destination table as a base template, and inserts the rows into an instance table named "{destination}{templateSuffix}". BigQuery will manage creation of the instance table, using the schema of the base template table. See https://cloud.google.com/bigquery/streaming-data-into-bigquery#template-tables for considerations when working with templates tables.',
    )
    traceId: Optional[str] = Field(
        None,
        description="Optional. Unique request trace id. Used for debugging purposes only. It is case-sensitive, limited to up to 36 ASCII characters. A UUID is recommended.",
    )


class TableDataList(BaseModel):
    etag: Optional[str] = Field(None, description="A hash of this page of results.")
    kind: Optional[str] = Field(
        "bigquery#tableDataList", description="The resource type of the response."
    )
    pageToken: Optional[str] = Field(
        None,
        description="A token used for paging results. Providing this token instead of the startIndex parameter can help you retrieve stable results when an underlying table is changing.",
    )
    rows: Optional[List[TableRow]] = Field(None, description="Rows of results.")
    totalRows: Optional[str] = Field(
        None,
        description="Total rows of the entire table. In order to show default value 0 we have to present it as string.",
    )


class Table1(BaseModel):
    clustering: Optional[Clustering] = Field(
        None, description="Clustering specification for this table, if configured."
    )
    creationTime: Optional[str] = Field(
        None,
        description="Output only. The time when this table was created, in milliseconds since the epoch.",
    )
    expirationTime: Optional[str] = Field(
        None,
        description="The time when this table expires, in milliseconds since the epoch. If not present, the table will persist indefinitely. Expired tables will be deleted and their storage reclaimed.",
    )
    friendlyName: Optional[str] = Field(
        None, description="The user-friendly name for this table."
    )
    id: Optional[str] = Field(None, description="An opaque ID of the table.")
    kind: Optional[str] = Field(None, description="The resource type.")
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="The labels associated with this table. You can use these to organize and group your tables.",
    )
    rangePartitioning: Optional[RangePartitioning] = Field(
        None, description="The range partitioning for this table."
    )
    requirePartitionFilter: Optional[bool] = Field(
        "false",
        description="Optional. If set to true, queries including this table must specify a partition filter. This filter is used for partition elimination.",
    )
    tableReference: Optional[TableReference] = Field(
        None, description="A reference uniquely identifying table."
    )
    timePartitioning: Optional[TimePartitioning] = Field(
        None, description="The time-based partitioning for this table."
    )
    type: Optional[str] = Field(None, description="The type of table.")
    view: Optional[View] = Field(None, description="Information about a logical view.")


class TableList(BaseModel):
    etag: Optional[str] = Field(None, description="A hash of this page of results.")
    kind: Optional[str] = Field("bigquery#tableList", description="The type of list.")
    nextPageToken: Optional[str] = Field(
        None, description="A token to request the next page of results."
    )
    tables: Optional[List[Table1]] = Field(
        None, description="Tables in the requested dataset."
    )
    totalItems: Optional[int] = Field(
        None, description="The total number of tables in the dataset."
    )


class TableMetadataCacheUsage(BaseModel):
    explanation: Optional[str] = Field(
        None,
        description="Free form human-readable reason metadata caching was unused for the job.",
    )
    staleness: Optional[str] = Field(
        None,
        description="Duration since last refresh as of this job for managed tables (indicates metadata cache staleness as seen by this job).",
    )
    tableReference: Optional[TableReference] = Field(
        None, description="Metadata caching eligible table referenced in the query."
    )
    tableType: Optional[str] = Field(
        None,
        description="[Table type](https://cloud.google.com/bigquery/docs/reference/rest/v2/tables#Table.FIELDS.type).",
    )
    unusedReason: Optional[UnusedReason] = Field(
        None, description="Reason for not using metadata caching for the table."
    )


class VectorSearchStatistics(BaseModel):
    indexUnusedReasons: Optional[List[IndexUnusedReason]] = Field(
        None,
        description="When `indexUsageMode` is `UNUSED` or `PARTIALLY_USED`, this field explains why indexes were not used in all or part of the vector search query. If `indexUsageMode` is `FULLY_USED`, this field is not populated.",
    )
    indexUsageMode: Optional[IndexUsageMode] = Field(
        None, description="Specifies the index usage mode for the query."
    )
    storedColumnsUsages: Optional[List[StoredColumnsUsage]] = Field(
        None,
        description="Specifies the usage of stored columns in the query when stored columns are used in the query.",
    )


class Cluster(BaseModel):
    centroidId: Optional[str] = Field(None, description="Centroid id.")
    count: Optional[str] = Field(
        None,
        description="Count of training data rows that were assigned to this cluster.",
    )
    featureValues: Optional[List[FeatureValue]] = Field(
        None, description="Values of highly variant features for this cluster."
    )


class ClusteringMetrics(BaseModel):
    clusters: Optional[List[Cluster]] = Field(
        None, description="Information for all clusters."
    )
    daviesBouldinIndex: Optional[float] = Field(
        None, description="Davies-Bouldin index."
    )
    meanSquaredDistance: Optional[float] = Field(
        None,
        description="Mean of squared distances between each sample to its cluster centroid.",
    )


class Acces(BaseModel):
    condition: Optional[Expr] = Field(
        None,
        description="Optional. condition for the binding. If CEL expression in this field is true, this access binding will be considered",
    )
    dataset: Optional[DatasetAccessEntry] = Field(
        None,
        description="[Pick one] A grant authorizing all resources of a particular type in a particular dataset access to this dataset. Only views are supported for now. The role field is not required when this field is set. If that dataset is deleted and re-created, its access needs to be granted again via an update operation.",
    )
    domain: Optional[str] = Field(
        None,
        description='[Pick one] A domain to grant access to. Any users signed in with the domain specified will be granted the specified access. Example: "example.com". Maps to IAM policy member "domain:DOMAIN".',
    )
    groupByEmail: Optional[str] = Field(
        None,
        description='[Pick one] An email address of a Google Group to grant access to. Maps to IAM policy member "group:GROUP".',
    )
    iamMember: Optional[str] = Field(
        None,
        description="[Pick one] Some other type of member that appears in the IAM Policy but isn't a user, group, domain, or special group.",
    )
    role: Optional[str] = Field(
        None,
        description='An IAM role ID that should be granted to the user, group, or domain specified in this access entry. The following legacy mappings will be applied: * `OWNER`: `roles/bigquery.dataOwner` * `WRITER`: `roles/bigquery.dataEditor` * `READER`: `roles/bigquery.dataViewer` This field will accept any of the above formats, but will return only the legacy format. For example, if you set this field to "roles/bigquery.dataOwner", it will be returned back as "OWNER".',
    )
    routine: Optional[RoutineReference] = Field(
        None,
        description="[Pick one] A routine from a different dataset to grant access to. Queries executed against that routine will have read access to views/tables/routines in this dataset. Only UDF is supported for now. The role field is not required when this field is set. If that routine is updated by any user, access to the routine needs to be granted again via an update operation.",
    )
    specialGroup: Optional[str] = Field(
        None,
        description="[Pick one] A special group to grant access to. Possible values include: * projectOwners: Owners of the enclosing project. * projectReaders: Readers of the enclosing project. * projectWriters: Writers of the enclosing project. * allAuthenticatedUsers: All authenticated BigQuery users. Maps to similarly-named IAM members.",
    )
    userByEmail: Optional[str] = Field(
        None,
        description='[Pick one] An email address of a user to grant access to. For example: fred@example.com. Maps to IAM policy member "user:EMAIL" or "serviceAccount:EMAIL".',
    )
    view: Optional[TableReference] = Field(
        None,
        description="[Pick one] A view from a different dataset to grant access to. Queries executed against that view will have read access to views/tables/routines in this dataset. The role field is not required when this field is set. If that view is updated by any user, access to the view needs to be granted again via an update operation.",
    )


class Dataset(BaseModel):
    tags: Optional[List[Tag]] = Field(
        None,
        description="Output only. Tags for the dataset. To provide tags as inputs, use the `resourceTags` field.",
    )
    access: Optional[List[Acces]] = Field(
        None,
        description="Optional. An array of objects that define dataset access for one or more entities. You can set this property when inserting or updating a dataset in order to control who is allowed to access the data. If unspecified at dataset creation time, BigQuery adds default dataset access for the following entities: access.specialGroup: projectReaders; access.role: READER; access.specialGroup: projectWriters; access.role: WRITER; access.specialGroup: projectOwners; access.role: OWNER; access.userByEmail: [dataset creator email]; access.role: OWNER; If you patch a dataset, then this field is overwritten by the patched dataset's access field. To add entities, you must supply the entire existing access array in addition to any new entities that you want to add.",
    )
    creationTime: Optional[str] = Field(
        None,
        description="Output only. The time when this dataset was created, in milliseconds since the epoch.",
    )
    datasetReference: Optional[DatasetReference] = Field(
        None, description="Required. A reference that identifies the dataset."
    )
    defaultCollation: Optional[str] = Field(
        None,
        description="Optional. Defines the default collation specification of future tables created in the dataset. If a table is created in this dataset without table-level default collation, then the table inherits the dataset default collation, which is applied to the string fields that do not have explicit collation specified. A change to this field affects only tables created afterwards, and does not alter the existing tables. The following values are supported: * 'und:ci': undetermined locale, case insensitive. * '': empty string. Default to case-sensitive behavior.",
    )
    defaultEncryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None,
        description="The default encryption key for all tables in the dataset. After this property is set, the encryption key of all newly-created tables in the dataset is set to this value unless the table creation request or query explicitly overrides the key.",
    )
    defaultPartitionExpirationMs: Optional[str] = Field(
        None,
        description="This default partition expiration, expressed in milliseconds. When new time-partitioned tables are created in a dataset where this property is set, the table will inherit this value, propagated as the `TimePartitioning.expirationMs` property on the new table. If you set `TimePartitioning.expirationMs` explicitly when creating a table, the `defaultPartitionExpirationMs` of the containing dataset is ignored. When creating a partitioned table, if `defaultPartitionExpirationMs` is set, the `defaultTableExpirationMs` value is ignored and the table will not be inherit a table expiration deadline.",
    )
    defaultRoundingMode: Optional[DefaultRoundingMode] = Field(
        None,
        description="Optional. Defines the default rounding mode specification of new tables created within this dataset. During table creation, if this field is specified, the table within this dataset will inherit the default rounding mode of the dataset. Setting the default rounding mode on a table overrides this option. Existing tables in the dataset are unaffected. If columns are defined during that table creation, they will immediately inherit the table's default rounding mode, unless otherwise specified.",
    )
    defaultTableExpirationMs: Optional[str] = Field(
        None,
        description="Optional. The default lifetime of all tables in the dataset, in milliseconds. The minimum lifetime value is 3600000 milliseconds (one hour). To clear an existing default expiration with a PATCH request, set to 0. Once this property is set, all newly-created tables in the dataset will have an expirationTime property set to the creation time plus the value in this property, and changing the value will only affect new tables, not existing ones. When the expirationTime for a given table is reached, that table will be deleted automatically. If a table's expirationTime is modified or removed before the table expires, or if you provide an explicit expirationTime when creating a table, that value takes precedence over the default expiration time indicated by this property.",
    )
    description: Optional[str] = Field(
        None, description="Optional. A user-friendly description of the dataset."
    )
    etag: Optional[str] = Field(
        None, description="Output only. A hash of the resource."
    )
    externalCatalogDatasetOptions: Optional[ExternalCatalogDatasetOptions] = Field(
        None,
        description="Optional. Options defining open source compatible datasets living in the BigQuery catalog. Contains metadata of open source database, schema or namespace represented by the current dataset.",
    )
    externalDatasetReference: Optional[ExternalDatasetReference] = Field(
        None,
        description="Optional. Reference to a read-only external dataset defined in data catalogs outside of BigQuery. Filled out when the dataset type is EXTERNAL.",
    )
    friendlyName: Optional[str] = Field(
        None, description="Optional. A descriptive name for the dataset."
    )
    id: Optional[str] = Field(
        None,
        description="Output only. The fully-qualified unique name of the dataset in the format projectId:datasetId. The dataset name without the project name is given in the datasetId field. When creating a new dataset, leave this field blank, and instead specify the datasetId field.",
    )
    isCaseInsensitive: Optional[bool] = Field(
        None,
        description="Optional. TRUE if the dataset and its table names are case-insensitive, otherwise FALSE. By default, this is FALSE, which means the dataset and its table names are case-sensitive. This field does not affect routine references.",
    )
    kind: Optional[str] = Field(
        "bigquery#dataset", description="Output only. The resource type."
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="The labels associated with this dataset. You can use these to organize and group your datasets. You can set this property when inserting or updating a dataset. See [Creating and Updating Dataset Labels](https://cloud.google.com/bigquery/docs/creating-managing-labels#creating_and_updating_dataset_labels) for more information.",
    )
    lastModifiedTime: Optional[str] = Field(
        None,
        description="Output only. The date when this dataset was last modified, in milliseconds since the epoch.",
    )
    linkedDatasetMetadata: Optional[LinkedDatasetMetadata] = Field(
        None,
        description="Output only. Metadata about the LinkedDataset. Filled out when the dataset type is LINKED.",
    )
    linkedDatasetSource: Optional[LinkedDatasetSource] = Field(
        None,
        description="Optional. The source dataset reference when the dataset is of type LINKED. For all other dataset types it is not set. This field cannot be updated once it is set. Any attempt to update this field using Update and Patch API Operations will be ignored.",
    )
    location: Optional[str] = Field(
        None,
        description="The geographic location where the dataset should reside. See https://cloud.google.com/bigquery/docs/locations for supported locations.",
    )
    maxTimeTravelHours: Optional[str] = Field(
        None,
        description="Optional. Defines the time travel window in hours. The value can be from 48 to 168 hours (2 to 7 days). The default value is 168 hours if this is not set.",
    )
    resourceTags: Optional[Dict[str, str]] = Field(
        None,
        description='Optional. The [tags](https://cloud.google.com/bigquery/docs/tags) attached to this dataset. Tag keys are globally unique. Tag key is expected to be in the namespaced format, for example "123456789012/environment" where 123456789012 is the ID of the parent organization or project resource for this tag key. Tag value is expected to be the short name, for example "Production". See [Tag definitions](https://cloud.google.com/iam/docs/tags-access-control#definitions) for more details.',
    )
    restrictions: Optional[RestrictionConfig] = Field(
        None,
        description="Optional. Output only. Restriction config for all tables and dataset. If set, restrict certain accesses on the dataset and all its tables based on the config. See [Data egress](https://cloud.google.com/bigquery/docs/analytics-hub-introduction#data_egress) for more details.",
    )
    satisfiesPzi: Optional[bool] = Field(
        None, description="Output only. Reserved for future use."
    )
    satisfiesPzs: Optional[bool] = Field(
        None, description="Output only. Reserved for future use."
    )
    selfLink: Optional[str] = Field(
        None,
        description="Output only. A URL that can be used to access the resource again. You can use this URL in Get or Update requests to the resource.",
    )
    storageBillingModel: Optional[StorageBillingModel] = Field(
        None, description="Optional. Updates storage_billing_model for the dataset."
    )
    type: Optional[str] = Field(
        None,
        description="Output only. Same as `type` in `ListFormatDataset`. The type of the dataset, one of: * DEFAULT - only accessible by owner and authorized accounts, * PUBLIC - accessible by everyone, * LINKED - linked dataset, * EXTERNAL - dataset with definition in external metadata catalog.",
    )

    def to_dataset1(self):
        return Dataset1(
            datasetReference=self.datasetReference,
            friendlyName=self.friendlyName,
            id=self.id,
            kind=self.kind,
            labels=self.labels,
            location=self.location,
        )


class EvaluationMetrics(BaseModel):
    arimaForecastingMetrics: Optional[ArimaForecastingMetrics] = Field(
        None, description="Populated for ARIMA models."
    )
    binaryClassificationMetrics: Optional[BinaryClassificationMetrics] = Field(
        None, description="Populated for binary classification/classifier models."
    )
    clusteringMetrics: Optional[ClusteringMetrics] = Field(
        None, description="Populated for clustering models."
    )
    dimensionalityReductionMetrics: Optional[DimensionalityReductionMetrics] = Field(
        None,
        description="Evaluation metrics when the model is a dimensionality reduction model, which currently includes PCA.",
    )
    multiClassClassificationMetrics: Optional[MultiClassClassificationMetrics] = Field(
        None, description="Populated for multi-class classification/classifier models."
    )
    rankingMetrics: Optional[RankingMetrics] = Field(
        None,
        description="Populated for implicit feedback type matrix factorization models.",
    )
    regressionMetrics: Optional[RegressionMetrics] = Field(
        None,
        description="Populated for regression models and explicit feedback type matrix factorization models.",
    )


class HparamSearchSpaces(BaseModel):
    activationFn: Optional[StringHparamSearchSpace] = Field(
        None, description="Activation functions of neural network models."
    )
    batchSize: Optional[IntHparamSearchSpace] = Field(
        None, description="Mini batch sample size."
    )
    boosterType: Optional[StringHparamSearchSpace] = Field(
        None, description="Booster type for boosted tree models."
    )
    colsampleBylevel: Optional[DoubleHparamSearchSpace] = Field(
        None,
        description="Subsample ratio of columns for each level for boosted tree models.",
    )
    colsampleBynode: Optional[DoubleHparamSearchSpace] = Field(
        None,
        description="Subsample ratio of columns for each node(split) for boosted tree models.",
    )
    colsampleBytree: Optional[DoubleHparamSearchSpace] = Field(
        None,
        description="Subsample ratio of columns when constructing each tree for boosted tree models.",
    )
    dartNormalizeType: Optional[StringHparamSearchSpace] = Field(
        None, description="Dart normalization type for boosted tree models."
    )
    dropout: Optional[DoubleHparamSearchSpace] = Field(
        None,
        description="Dropout probability for dnn model training and boosted tree models using dart booster.",
    )
    hiddenUnits: Optional[IntArrayHparamSearchSpace] = Field(
        None, description="Hidden units for neural network models."
    )
    l1Reg: Optional[DoubleHparamSearchSpace] = Field(
        None, description="L1 regularization coefficient."
    )
    l2Reg: Optional[DoubleHparamSearchSpace] = Field(
        None, description="L2 regularization coefficient."
    )
    learnRate: Optional[DoubleHparamSearchSpace] = Field(
        None, description="Learning rate of training jobs."
    )
    maxTreeDepth: Optional[IntHparamSearchSpace] = Field(
        None, description="Maximum depth of a tree for boosted tree models."
    )
    minSplitLoss: Optional[DoubleHparamSearchSpace] = Field(
        None, description="Minimum split loss for boosted tree models."
    )
    minTreeChildWeight: Optional[IntHparamSearchSpace] = Field(
        None,
        description="Minimum sum of instance weight needed in a child for boosted tree models.",
    )
    numClusters: Optional[IntHparamSearchSpace] = Field(
        None, description="Number of clusters for k-means."
    )
    numFactors: Optional[IntHparamSearchSpace] = Field(
        None, description="Number of latent factors to train on."
    )
    numParallelTree: Optional[IntHparamSearchSpace] = Field(
        None, description="Number of parallel trees for boosted tree models."
    )
    optimizer: Optional[StringHparamSearchSpace] = Field(
        None, description="Optimizer of TF models."
    )
    subsample: Optional[DoubleHparamSearchSpace] = Field(
        None,
        description="Subsample the training data to grow tree to prevent overfitting for boosted tree models.",
    )
    treeMethod: Optional[StringHparamSearchSpace] = Field(
        None, description="Tree construction algorithm for boosted tree models."
    )
    walsAlpha: Optional[DoubleHparamSearchSpace] = Field(
        None,
        description="Hyperparameter for matrix factoration when implicit feedback type is specified.",
    )


class HparamTuningTrial(BaseModel):
    endTimeMs: Optional[str] = Field(None, description="Ending time of the trial.")
    errorMessage: Optional[str] = Field(
        None, description="Error message for FAILED and INFEASIBLE trial."
    )
    evalLoss: Optional[float] = Field(
        None, description="Loss computed on the eval data at the end of trial."
    )
    evaluationMetrics: Optional[EvaluationMetrics] = Field(
        None,
        description="Evaluation metrics of this trial calculated on the test data. Empty in Job API.",
    )
    hparamTuningEvaluationMetrics: Optional[EvaluationMetrics] = Field(
        None,
        description="Hyperparameter tuning evaluation metrics of this trial calculated on the eval data. Unlike evaluation_metrics, only the fields corresponding to the hparam_tuning_objectives are set.",
    )
    hparams: Optional[TrainingOptionsModel] = Field(
        None, description="The hyperprameters selected for this trial."
    )
    startTimeMs: Optional[str] = Field(None, description="Starting time of the trial.")
    status: Optional[Status] = Field(None, description="The status of the trial.")
    trainingLoss: Optional[float] = Field(
        None, description="Loss computed on the training data at the end of trial."
    )
    trialId: Optional[str] = Field(None, description="1-based index of the trial.")


class ListRowAccessPoliciesResponse(BaseModel):
    nextPageToken: Optional[str] = Field(
        None, description="A token to request the next page of results."
    )
    rowAccessPolicies: Optional[List[RowAccessPolicy]] = Field(
        None, description="Row access policies on the requested table."
    )


class MetadataCacheStatistics(BaseModel):
    tableMetadataCacheUsage: Optional[List[TableMetadataCacheUsage]] = Field(
        None,
        description="Set for the Metadata caching eligible tables referenced in the query.",
    )


class MlStatistics(BaseModel):
    hparamTrials: Optional[List[HparamTuningTrial]] = Field(
        None,
        description="Output only. Trials of a [hyperparameter tuning job](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview) sorted by trial_id.",
    )
    iterationResults: Optional[List[IterationResult]] = Field(
        None,
        description="Results for all completed iterations. Empty for [hyperparameter tuning jobs](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview).",
    )
    maxIterations: Optional[str] = Field(
        None,
        description="Output only. Maximum number of iterations specified as max_iterations in the 'CREATE MODEL' query. The actual number of iterations may be less than this number due to early stop.",
    )
    modelType: Optional[ModelType] = Field(
        None, description="Output only. The type of the model that is being trained."
    )
    trainingType: Optional[TrainingType] = Field(
        None, description="Output only. Training type of the job."
    )


class PerformanceInsights(BaseModel):
    avgPreviousExecutionMs: Optional[str] = Field(
        None,
        description="Output only. Average execution ms of previous runs. Indicates the job ran slow compared to previous executions. To find previous executions, use INFORMATION_SCHEMA tables and filter jobs with same query hash.",
    )
    stagePerformanceChangeInsights: Optional[List[StagePerformanceChangeInsight]] = (
        Field(
            None,
            description="Output only. Query stage performance insights compared to previous runs, for diagnosing performance regression.",
        )
    )
    stagePerformanceStandaloneInsights: Optional[
        List[StagePerformanceStandaloneInsight]
    ] = Field(
        None,
        description="Output only. Standalone query stage performance insights, for exploring potential improvements.",
    )


class TrainingRun(BaseModel):
    classLevelGlobalExplanations: Optional[List[GlobalExplanation]] = Field(
        None,
        description="Output only. Global explanation contains the explanation of top features on the class level. Applies to classification models only.",
    )
    dataSplitResult: Optional[DataSplitResult] = Field(
        None,
        description="Output only. Data split result of the training run. Only set when the input data is actually split.",
    )
    evaluationMetrics: Optional[EvaluationMetrics] = Field(
        None,
        description="Output only. The evaluation metrics over training/eval data that were computed at the end of training.",
    )
    modelLevelGlobalExplanation: Optional[GlobalExplanation] = Field(
        None,
        description="Output only. Global explanation contains the explanation of top features on the model level. Applies to both regression and classification models.",
    )
    results: Optional[List[IterationResult]] = Field(
        None,
        description="Output only. Output of each iteration run, results.size() <= max_iterations.",
    )
    startTime: Optional[str] = Field(
        None, description="Output only. The start time of this training run."
    )
    trainingOptions: Optional[TrainingOptionsModel] = Field(
        None,
        description="Output only. Options that were used for this training run, includes user specified and default options that were used.",
    )
    trainingStartTime: Optional[str] = Field(
        None,
        description="Output only. The start time of this training run, in milliseconds since epoch.",
    )
    vertexAiModelId: Optional[str] = Field(
        None,
        description="The model id in the [Vertex AI Model Registry](https://cloud.google.com/vertex-ai/docs/model-registry/introduction) for this training run.",
    )
    vertexAiModelVersion: Optional[str] = Field(
        None,
        description="Output only. The model version in the [Vertex AI Model Registry](https://cloud.google.com/vertex-ai/docs/model-registry/introduction) for this training run.",
    )


class Argument(BaseModel):
    argumentKind: Optional[ArgumentKind] = Field(
        None, description="Optional. Defaults to FIXED_TYPE."
    )
    dataType: Optional[StandardSqlDataType] = Field(
        None, description="Set if argument_kind == FIXED_TYPE."
    )
    isAggregate: Optional[bool] = Field(
        None,
        description='Optional. Whether the argument is an aggregate function parameter. Must be Unset for routine types other than AGGREGATE_FUNCTION. For AGGREGATE_FUNCTION, if set to false, it is equivalent to adding "NOT AGGREGATE" clause in DDL; Otherwise, it is equivalent to omitting "NOT AGGREGATE" clause in DDL.',
    )
    mode: Optional[Mode] = Field(
        None,
        description="Optional. Specifies whether the argument is input or output. Can be set for procedures only.",
    )
    name: Optional[str] = Field(
        None,
        description="Optional. The name of this argument. Can be absent for function return argument.",
    )


class Job(BaseModel):
    configuration: Optional[JobConfiguration] = Field(
        None, description="Required. Describes the job configuration."
    )
    etag: Optional[str] = Field(
        None, description="Output only. A hash of this resource."
    )
    id: Optional[str] = Field(
        None, description="Output only. Opaque ID field of the job."
    )
    jobCreationReason: Optional[JobCreationReason] = Field(
        None,
        description="Output only. The reason why a Job was created. [Preview](https://cloud.google.com/products/#product-launch-stages)",
    )
    jobReference: Optional[JobReference] = Field(
        None,
        description="Optional. Reference describing the unique-per-user name of the job.",
    )
    kind: Optional[str] = Field(
        "bigquery#job", description="Output only. The type of the resource."
    )
    principal_subject: Optional[str] = Field(
        None,
        description="Output only. [Full-projection-only] String representation of identity of requesting party. Populated for both first- and third-party identities. Only present for APIs that support third-party identities.",
    )
    selfLink: Optional[str] = Field(
        None,
        description="Output only. A URL that can be used to access the resource again.",
    )
    statistics: Optional[JobStatistics] = Field(
        None,
        description="Output only. Information about the job, including starting time and ending time of the job.",
    )
    status: Optional[JobStatus] = Field(
        None,
        description="Output only. The status of this job. Examine this value when polling an asynchronous job to see if the job is complete.",
    )
    user_email: Optional[str] = Field(
        None, description="Output only. Email address of the user who ran the job."
    )


class JobCancelResponse(BaseModel):
    job: Optional[Job] = Field(None, description="The final state of the job.")
    kind: Optional[str] = Field(
        "bigquery#jobCancelResponse", description="The resource type of the response."
    )


class JobConfiguration(BaseModel):
    copy_: Optional[JobConfigurationTableCopy] = Field(
        None, alias="copy", description="[Pick one] Copies a table."
    )
    dryRun: Optional[bool] = Field(
        None,
        description="Optional. If set, don't actually run this job. A valid query will return a mostly empty response with some processing statistics, while an invalid query will return the same error it would if it wasn't a dry run. Behavior of non-query jobs is undefined.",
    )
    extract: Optional[JobConfigurationExtract] = Field(
        None, description="[Pick one] Configures an extract job."
    )
    jobTimeoutMs: Optional[str] = Field(
        None,
        description="Optional. Job timeout in milliseconds. If this time limit is exceeded, BigQuery will attempt to stop a longer job, but may not always succeed in canceling it before the job completes. For example, a job that takes more than 60 seconds to complete has a better chance of being stopped than a job that takes 10 seconds to complete.",
    )
    jobType: Optional[str] = Field(
        None,
        description="Output only. The type of the job. Can be QUERY, LOAD, EXTRACT, COPY or UNKNOWN.",
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="The labels associated with this job. You can use these to organize and group your jobs. Label keys and values can be no longer than 63 characters, can only contain lowercase letters, numeric characters, underscores and dashes. International characters are allowed. Label values are optional. Label keys must start with a letter and each label in the list must have a different key.",
    )
    load: Optional[JobConfigurationLoad] = Field(
        None, description="[Pick one] Configures a load job."
    )
    query: Optional[JobConfigurationQuery] = Field(
        None, description="[Pick one] Configures a query job."
    )
    reservation: Optional[str] = Field(
        None,
        description="Optional. The reservation that job would use. User can specify a reservation to execute the job. If reservation is not set, reservation is determined based on the rules defined by the reservation assignments. The expected format is `projects/{project}/locations/{location}/reservations/{reservation}`.",
    )


class JobConfigurationQuery(BaseModel):
    allowLargeResults: Optional[bool] = Field(
        False,
        description="Optional. If true and query uses legacy SQL dialect, allows the query to produce arbitrarily large result tables at a slight cost in performance. Requires destinationTable to be set. For GoogleSQL queries, this flag is ignored and large results are always allowed. However, you must still set destinationTable when result size exceeds the allowed maximum response size.",
    )
    clustering: Optional[Clustering] = Field(
        None, description="Clustering specification for the destination table."
    )
    connectionProperties: Optional[List[ConnectionProperty]] = Field(
        None, description="Connection properties which can modify the query behavior."
    )
    continuous: Optional[bool] = Field(
        None,
        description="[Optional] Specifies whether the query should be executed as a continuous query. The default value is false.",
    )
    createDisposition: Optional[str] = Field(
        None,
        description="Optional. Specifies whether the job is allowed to create new tables. The following values are supported: * CREATE_IF_NEEDED: If the table does not exist, BigQuery creates the table. * CREATE_NEVER: The table must already exist. If it does not, a 'notFound' error is returned in the job result. The default value is CREATE_IF_NEEDED. Creation, truncation and append actions occur as one atomic update upon job completion.",
    )
    createSession: Optional[bool] = Field(
        None,
        description="If this property is true, the job creates a new session using a randomly generated session_id. To continue using a created session with subsequent queries, pass the existing session identifier as a `ConnectionProperty` value. The session identifier is returned as part of the `SessionInfo` message within the query statistics. The new session's location will be set to `Job.JobReference.location` if it is present, otherwise it's set to the default location based on existing routing logic.",
    )
    defaultDataset: Optional[DatasetReference] = Field(
        None,
        description="Optional. Specifies the default dataset to use for unqualified table names in the query. This setting does not alter behavior of unqualified dataset names. Setting the system variable `@@dataset_id` achieves the same behavior. See https://cloud.google.com/bigquery/docs/reference/system-variables for more information on system variables.",
    )
    destinationEncryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None, description="Custom encryption configuration (e.g., Cloud KMS keys)"
    )
    destinationTable: Optional[TableReference] = Field(
        None,
        description="Optional. Describes the table where the query results should be stored. This property must be set for large results that exceed the maximum response size. For queries that produce anonymous (cached) results, this field will be populated by BigQuery.",
    )
    flattenResults: Optional[bool] = Field(
        True,
        description="Optional. If true and query uses legacy SQL dialect, flattens all nested and repeated fields in the query results. allowLargeResults must be true if this is set to false. For GoogleSQL queries, this flag is ignored and results are never flattened.",
    )
    maximumBillingTier: Optional[int] = Field(
        1,
        description="Optional. [Deprecated] Maximum billing tier allowed for this query. The billing tier controls the amount of compute resources allotted to the query, and multiplies the on-demand cost of the query accordingly. A query that runs within its allotted resources will succeed and indicate its billing tier in statistics.query.billingTier, but if the query exceeds its allotted resources, it will fail with billingTierLimitExceeded. WARNING: The billed byte amount can be multiplied by an amount up to this number! Most users should not need to alter this setting, and we recommend that you avoid introducing new uses of it.",
    )
    maximumBytesBilled: Optional[str] = Field(
        None,
        description="Limits the bytes billed for this job. Queries that will have bytes billed beyond this limit will fail (without incurring a charge). If unspecified, this will be set to your project default.",
    )
    parameterMode: Optional[str] = Field(
        None,
        description="GoogleSQL only. Set to POSITIONAL to use positional (?) query parameters or to NAMED to use named (@myparam) query parameters in this query.",
    )
    preserveNulls: Optional[bool] = Field(
        None, description="[Deprecated] This property is deprecated."
    )
    priority: Optional[str] = Field(
        None,
        description="Optional. Specifies a priority for the query. Possible values include INTERACTIVE and BATCH. The default value is INTERACTIVE.",
    )
    query: Optional[str] = Field(
        None,
        description="[Required] SQL query text to execute. The useLegacySql field can be used to indicate whether the query uses legacy SQL or GoogleSQL.",
    )
    queryParameters: Optional[List[QueryParameter]] = Field(
        None, description="Query parameters for GoogleSQL queries."
    )
    rangePartitioning: Optional[RangePartitioning] = Field(
        None,
        description="Range partitioning specification for the destination table. Only one of timePartitioning and rangePartitioning should be specified.",
    )
    schemaUpdateOptions: Optional[List[str]] = Field(
        None,
        description="Allows the schema of the destination table to be updated as a side effect of the query job. Schema update options are supported in two cases: when writeDisposition is WRITE_APPEND; when writeDisposition is WRITE_TRUNCATE and the destination table is a partition of a table, specified by partition decorators. For normal tables, WRITE_TRUNCATE will always overwrite the schema. One or more of the following values are specified: * ALLOW_FIELD_ADDITION: allow adding a nullable field to the schema. * ALLOW_FIELD_RELAXATION: allow relaxing a required field in the original schema to nullable.",
    )
    scriptOptions: Optional[ScriptOptions] = Field(
        None, description="Options controlling the execution of scripts."
    )
    systemVariables: Optional[SystemVariables] = Field(
        None,
        description='Output only. System variables for GoogleSQL queries. A system variable is output if the variable is settable and its value differs from the system default. "@@" prefix is not included in the name of the System variables.',
    )
    tableDefinitions: Optional[Dict[str, ExternalDataConfiguration]] = Field(
        None,
        description="Optional. You can specify external table definitions, which operate as ephemeral tables that can be queried. These definitions are configured using a JSON map, where the string key represents the table identifier, and the value is the corresponding external data configuration object.",
    )
    timePartitioning: Optional[TimePartitioning] = Field(
        None,
        description="Time-based partitioning specification for the destination table. Only one of timePartitioning and rangePartitioning should be specified.",
    )
    useLegacySql: Optional[bool] = Field(
        True,
        description="Optional. Specifies whether to use BigQuery's legacy SQL dialect for this query. The default value is true. If set to false, the query will use BigQuery's GoogleSQL: https://cloud.google.com/bigquery/sql-reference/ When useLegacySql is set to false, the value of flattenResults is ignored; query will be run as if flattenResults is false.",
    )
    useQueryCache: Optional[bool] = Field(
        True,
        description="Optional. Whether to look for the result in the query cache. The query cache is a best-effort cache that will be flushed whenever tables in the query are modified. Moreover, the query cache is only available when a query does not have a destination table specified. The default value is true.",
    )
    userDefinedFunctionResources: Optional[List[UserDefinedFunctionResource]] = Field(
        None, description="Describes user-defined function resources used in the query."
    )
    writeDisposition: Optional[str] = Field(
        None,
        description="Optional. Specifies the action that occurs if the destination table already exists. The following values are supported: * WRITE_TRUNCATE: If the table already exists, BigQuery overwrites the data, removes the constraints, and uses the schema from the query result. * WRITE_APPEND: If the table already exists, BigQuery appends the data to the table. * WRITE_EMPTY: If the table already exists and contains data, a 'duplicate' error is returned in the job result. The default value is WRITE_EMPTY. Each action is atomic and only occurs if BigQuery is able to complete the job successfully. Creation, truncation and append actions occur as one atomic update upon job completion.",
    )
    writeIncrementalResults: Optional[bool] = Field(
        None,
        description="Optional. This is only supported for a SELECT query using a temporary table. If set, the query is allowed to write results incrementally to the temporary result table. This may incur a performance penalty. This option cannot be used with Legacy SQL. This feature is not yet available.",
    )


class Job1(BaseModel):
    configuration: Optional[JobConfiguration] = Field(
        None, description="Required. Describes the job configuration."
    )
    errorResult: Optional[ErrorProto] = Field(
        None,
        description="A result object that will be present only if the job has failed.",
    )
    id: Optional[str] = Field(None, description="Unique opaque ID of the job.")
    jobReference: Optional[JobReference] = Field(
        None, description="Unique opaque ID of the job."
    )
    kind: Optional[str] = Field(None, description="The resource type.")
    principal_subject: Optional[str] = Field(
        None,
        description="[Full-projection-only] String representation of identity of requesting party. Populated for both first- and third-party identities. Only present for APIs that support third-party identities.",
    )
    state: Optional[str] = Field(
        None,
        description="Running state of the job. When the state is DONE, errorResult can be checked to determine whether the job succeeded or failed.",
    )
    statistics: Optional[JobStatistics] = Field(
        None,
        description="Output only. Information about the job, including starting time and ending time of the job.",
    )
    status: Optional[JobStatus] = Field(
        None, description="[Full-projection-only] Describes the status of this job."
    )
    user_email: Optional[str] = Field(
        None,
        description="[Full-projection-only] Email address of the user who ran the job.",
    )


class JobList(BaseModel):
    etag: Optional[str] = Field(None, description="A hash of this page of results.")
    jobs: Optional[List[Job1]] = Field(
        None, description="List of jobs that were requested."
    )
    kind: Optional[str] = Field(
        "bigquery#jobList", description="The resource type of the response."
    )
    nextPageToken: Optional[str] = Field(
        None, description="A token to request the next page of results."
    )
    unreachable: Optional[List[str]] = Field(
        None,
        description='A list of skipped locations that were unreachable. For more information about BigQuery locations, see: https://cloud.google.com/bigquery/docs/locations. Example: "europe-west5"',
    )


class JobStatistics(BaseModel):
    completionRatio: Optional[float] = Field(
        None,
        description="Output only. [TrustedTester] Job progress (0.0 -> 1.0) for LOAD and EXTRACT jobs.",
    )
    copy_: Optional[JobStatistics5] = Field(
        None, alias="copy", description="Output only. Statistics for a copy job."
    )
    creationTime: Optional[str] = Field(
        None,
        description="Output only. Creation time of this job, in milliseconds since the epoch. This field will be present on all jobs.",
    )
    dataMaskingStatistics: Optional[DataMaskingStatistics] = Field(
        None,
        description="Output only. Statistics for data-masking. Present only for query and extract jobs.",
    )
    edition: Optional[Edition] = Field(
        None,
        description="Output only. Name of edition corresponding to the reservation for this job at the time of this update.",
    )
    endTime: Optional[str] = Field(
        None,
        description="Output only. End time of this job, in milliseconds since the epoch. This field will be present whenever a job is in the DONE state.",
    )
    extract: Optional[JobStatistics4] = Field(
        None, description="Output only. Statistics for an extract job."
    )
    finalExecutionDurationMs: Optional[str] = Field(
        None,
        description="Output only. The duration in milliseconds of the execution of the final attempt of this job, as BigQuery may internally re-attempt to execute the job.",
    )
    load: Optional[JobStatistics3] = Field(
        None, description="Output only. Statistics for a load job."
    )
    numChildJobs: Optional[str] = Field(
        None, description="Output only. Number of child jobs executed."
    )
    parentJobId: Optional[str] = Field(
        None,
        description="Output only. If this is a child job, specifies the job ID of the parent.",
    )
    query: Optional[JobStatistics2] = Field(
        None, description="Output only. Statistics for a query job."
    )
    quotaDeferments: Optional[List[str]] = Field(
        None, description="Output only. Quotas which delayed this job's start time."
    )
    reservationUsage: Optional[List[ReservationUsageItem]] = Field(
        None,
        description="Output only. Job resource usage breakdown by reservation. This field reported misleading information and will no longer be populated.",
    )
    reservation_id: Optional[str] = Field(
        None,
        description="Output only. Name of the primary reservation assigned to this job. Note that this could be different than reservations reported in the reservation usage field if parent reservations were used to execute this job.",
    )
    rowLevelSecurityStatistics: Optional[RowLevelSecurityStatistics] = Field(
        None,
        description="Output only. Statistics for row-level security. Present only for query and extract jobs.",
    )
    scriptStatistics: Optional[ScriptStatistics] = Field(
        None,
        description="Output only. If this a child job of a script, specifies information about the context of this job within the script.",
    )
    sessionInfo: Optional[SessionInfo] = Field(
        None,
        description="Output only. Information of the session if this job is part of one.",
    )
    startTime: Optional[str] = Field(
        None,
        description="Output only. Start time of this job, in milliseconds since the epoch. This field will be present when the job transitions from the PENDING state to either RUNNING or DONE.",
    )
    totalBytesProcessed: Optional[str] = Field(
        None, description="Output only. Total bytes processed for the job."
    )
    totalSlotMs: Optional[str] = Field(
        None, description="Output only. Slot-milliseconds for the job."
    )
    transactionInfo: Optional[TransactionInfo] = Field(
        None,
        description="Output only. [Alpha] Information of the multi-statement transaction if this job is part of one. This property is only expected on a child job or a job that is in a session. A script parent job is not part of the transaction started in the script.",
    )


class JobStatistics2(BaseModel):
    biEngineStatistics: Optional[BiEngineStatistics] = Field(
        None, description="Output only. BI Engine specific Statistics."
    )
    billingTier: Optional[int] = Field(
        None,
        description='Output only. Billing tier for the job. This is a BigQuery-specific concept which is not related to the Google Cloud notion of "free tier". The value here is a measure of the query\'s resource consumption relative to the amount of data scanned. For on-demand queries, the limit is 100, and all queries within this limit are billed at the standard on-demand rates. On-demand queries that exceed this limit will fail with a billingTierLimitExceeded error.',
    )
    cacheHit: Optional[bool] = Field(
        None,
        description="Output only. Whether the query result was fetched from the query cache.",
    )
    dclTargetDataset: Optional[DatasetReference] = Field(
        None, description="Output only. Referenced dataset for DCL statement."
    )
    dclTargetTable: Optional[TableReference] = Field(
        None, description="Output only. Referenced table for DCL statement."
    )
    dclTargetView: Optional[TableReference] = Field(
        None, description="Output only. Referenced view for DCL statement."
    )
    ddlAffectedRowAccessPolicyCount: Optional[str] = Field(
        None,
        description="Output only. The number of row access policies affected by a DDL statement. Present only for DROP ALL ROW ACCESS POLICIES queries.",
    )
    ddlDestinationTable: Optional[TableReference] = Field(
        None,
        description="Output only. The table after rename. Present only for ALTER TABLE RENAME TO query.",
    )
    ddlOperationPerformed: Optional[str] = Field(
        None,
        description="Output only. The DDL operation performed, possibly dependent on the pre-existence of the DDL target.",
    )
    ddlTargetDataset: Optional[DatasetReference] = Field(
        None,
        description="Output only. The DDL target dataset. Present only for CREATE/ALTER/DROP SCHEMA(dataset) queries.",
    )
    ddlTargetRoutine: Optional[RoutineReference] = Field(
        None,
        description="Output only. [Beta] The DDL target routine. Present only for CREATE/DROP FUNCTION/PROCEDURE queries.",
    )
    ddlTargetRowAccessPolicy: Optional[RowAccessPolicyReference] = Field(
        None,
        description="Output only. The DDL target row access policy. Present only for CREATE/DROP ROW ACCESS POLICY queries.",
    )
    ddlTargetTable: Optional[TableReference] = Field(
        None,
        description="Output only. The DDL target table. Present only for CREATE/DROP TABLE/VIEW and DROP ALL ROW ACCESS POLICIES queries.",
    )
    dmlStats: Optional[DmlStatistics] = Field(
        None,
        description="Output only. Detailed statistics for DML statements INSERT, UPDATE, DELETE, MERGE or TRUNCATE.",
    )
    estimatedBytesProcessed: Optional[str] = Field(
        None,
        description="Output only. The original estimate of bytes processed for the job.",
    )
    exportDataStatistics: Optional[ExportDataStatistics] = Field(
        None, description="Output only. Stats for EXPORT DATA statement."
    )
    externalServiceCosts: Optional[List[ExternalServiceCost]] = Field(
        None,
        description="Output only. Job cost breakdown as bigquery internal cost and external service costs.",
    )
    loadQueryStatistics: Optional[LoadQueryStatistics] = Field(
        None, description="Output only. Statistics for a LOAD query."
    )
    materializedViewStatistics: Optional[MaterializedViewStatistics] = Field(
        None,
        description="Output only. Statistics of materialized views of a query job.",
    )
    metadataCacheStatistics: Optional[MetadataCacheStatistics] = Field(
        None,
        description="Output only. Statistics of metadata cache usage in a query for BigLake tables.",
    )
    mlStatistics: Optional[MlStatistics] = Field(
        None, description="Output only. Statistics of a BigQuery ML training job."
    )
    modelTraining: Optional[BigQueryModelTraining] = Field(
        None, description="Deprecated."
    )
    modelTrainingCurrentIteration: Optional[int] = Field(
        None, description="Deprecated."
    )
    modelTrainingExpectedTotalIteration: Optional[str] = Field(
        None, description="Deprecated."
    )
    numDmlAffectedRows: Optional[str] = Field(
        None,
        description="Output only. The number of rows affected by a DML statement. Present only for DML statements INSERT, UPDATE or DELETE.",
    )
    performanceInsights: Optional[PerformanceInsights] = Field(
        None, description="Output only. Performance insights."
    )
    queryInfo: Optional[QueryInfo] = Field(
        None, description="Output only. Query optimization information for a QUERY job."
    )
    queryPlan: Optional[List[ExplainQueryStage]] = Field(
        None, description="Output only. Describes execution plan for the query."
    )
    referencedRoutines: Optional[List[RoutineReference]] = Field(
        None, description="Output only. Referenced routines for the job."
    )
    referencedTables: Optional[List[TableReference]] = Field(
        None,
        description="Output only. Referenced tables for the job. Queries that reference more than 50 tables will not have a complete list.",
    )
    reservationUsage: Optional[List[ReservationUsageItem]] = Field(
        None,
        description="Output only. Job resource usage breakdown by reservation. This field reported misleading information and will no longer be populated.",
    )
    schema_: Optional[TableSchema] = Field(
        None,
        alias="schema",
        description="Output only. The schema of the results. Present only for successful dry run of non-legacy SQL queries.",
    )
    searchStatistics: Optional[SearchStatistics] = Field(
        None, description="Output only. Search query specific statistics."
    )
    sparkStatistics: Optional[SparkStatistics] = Field(
        None, description="Output only. Statistics of a Spark procedure job."
    )
    statementType: Optional[str] = Field(
        None,
        description="Output only. The type of query statement, if valid. Possible values: * `SELECT`: [`SELECT`](https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax#select_list) statement. * `ASSERT`: [`ASSERT`](https://cloud.google.com/bigquery/docs/reference/standard-sql/debugging-statements#assert) statement. * `INSERT`: [`INSERT`](https://cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax#insert_statement) statement. * `UPDATE`: [`UPDATE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax#update_statement) statement. * `DELETE`: [`DELETE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-manipulation-language) statement. * `MERGE`: [`MERGE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-manipulation-language) statement. * `CREATE_TABLE`: [`CREATE TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_table_statement) statement, without `AS SELECT`. * `CREATE_TABLE_AS_SELECT`: [`CREATE TABLE AS SELECT`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_table_statement) statement. * `CREATE_VIEW`: [`CREATE VIEW`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_view_statement) statement. * `CREATE_MODEL`: [`CREATE MODEL`](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-create#create_model_statement) statement. * `CREATE_MATERIALIZED_VIEW`: [`CREATE MATERIALIZED VIEW`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_materialized_view_statement) statement. * `CREATE_FUNCTION`: [`CREATE FUNCTION`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_function_statement) statement. * `CREATE_TABLE_FUNCTION`: [`CREATE TABLE FUNCTION`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_table_function_statement) statement. * `CREATE_PROCEDURE`: [`CREATE PROCEDURE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_procedure) statement. * `CREATE_ROW_ACCESS_POLICY`: [`CREATE ROW ACCESS POLICY`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_row_access_policy_statement) statement. * `CREATE_SCHEMA`: [`CREATE SCHEMA`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_schema_statement) statement. * `CREATE_SNAPSHOT_TABLE`: [`CREATE SNAPSHOT TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_snapshot_table_statement) statement. * `CREATE_SEARCH_INDEX`: [`CREATE SEARCH INDEX`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_search_index_statement) statement. * `DROP_TABLE`: [`DROP TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_table_statement) statement. * `DROP_EXTERNAL_TABLE`: [`DROP EXTERNAL TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_external_table_statement) statement. * `DROP_VIEW`: [`DROP VIEW`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_view_statement) statement. * `DROP_MODEL`: [`DROP MODEL`](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-drop-model) statement. * `DROP_MATERIALIZED_VIEW`: [`DROP MATERIALIZED VIEW`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_materialized_view_statement) statement. * `DROP_FUNCTION` : [`DROP FUNCTION`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_function_statement) statement. * `DROP_TABLE_FUNCTION` : [`DROP TABLE FUNCTION`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_table_function) statement. * `DROP_PROCEDURE`: [`DROP PROCEDURE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_procedure_statement) statement. * `DROP_SEARCH_INDEX`: [`DROP SEARCH INDEX`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_search_index) statement. * `DROP_SCHEMA`: [`DROP SCHEMA`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_schema_statement) statement. * `DROP_SNAPSHOT_TABLE`: [`DROP SNAPSHOT TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_snapshot_table_statement) statement. * `DROP_ROW_ACCESS_POLICY`: [`DROP [ALL] ROW ACCESS POLICY|POLICIES`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#drop_row_access_policy_statement) statement. * `ALTER_TABLE`: [`ALTER TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#alter_table_set_options_statement) statement. * `ALTER_VIEW`: [`ALTER VIEW`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#alter_view_set_options_statement) statement. * `ALTER_MATERIALIZED_VIEW`: [`ALTER MATERIALIZED VIEW`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#alter_materialized_view_set_options_statement) statement. * `ALTER_SCHEMA`: [`ALTER SCHEMA`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#alter_schema_set_options_statement) statement. * `SCRIPT`: [`SCRIPT`](https://cloud.google.com/bigquery/docs/reference/standard-sql/procedural-language). * `TRUNCATE_TABLE`: [`TRUNCATE TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax#truncate_table_statement) statement. * `CREATE_EXTERNAL_TABLE`: [`CREATE EXTERNAL TABLE`](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language#create_external_table_statement) statement. * `EXPORT_DATA`: [`EXPORT DATA`](https://cloud.google.com/bigquery/docs/reference/standard-sql/other-statements#export_data_statement) statement. * `EXPORT_MODEL`: [`EXPORT MODEL`](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-export-model) statement. * `LOAD_DATA`: [`LOAD DATA`](https://cloud.google.com/bigquery/docs/reference/standard-sql/other-statements#load_data_statement) statement. * `CALL`: [`CALL`](https://cloud.google.com/bigquery/docs/reference/standard-sql/procedural-language#call) statement.",
    )
    timeline: Optional[List[QueryTimelineSample]] = Field(
        None, description="Output only. Describes a timeline of job execution."
    )
    totalBytesBilled: Optional[str] = Field(
        None,
        description="Output only. If the project is configured to use on-demand pricing, then this field contains the total bytes billed for the job. If the project is configured to use flat-rate pricing, then you are not billed for bytes and this field is informational only.",
    )
    totalBytesProcessed: Optional[str] = Field(
        None, description="Output only. Total bytes processed for the job."
    )
    totalBytesProcessedAccuracy: Optional[str] = Field(
        None,
        description="Output only. For dry-run jobs, totalBytesProcessed is an estimate and this field specifies the accuracy of the estimate. Possible values can be: UNKNOWN: accuracy of the estimate is unknown. PRECISE: estimate is precise. LOWER_BOUND: estimate is lower bound of what the query would cost. UPPER_BOUND: estimate is upper bound of what the query would cost.",
    )
    totalPartitionsProcessed: Optional[str] = Field(
        None,
        description="Output only. Total number of partitions processed from all partitioned tables referenced in the job.",
    )
    totalSlotMs: Optional[str] = Field(
        None, description="Output only. Slot-milliseconds for the job."
    )
    transferredBytes: Optional[str] = Field(
        None,
        description="Output only. Total bytes transferred for cross-cloud queries such as Cross Cloud Transfer and CREATE TABLE AS SELECT (CTAS).",
    )
    undeclaredQueryParameters: Optional[List[QueryParameter]] = Field(
        None,
        description="Output only. GoogleSQL only: list of undeclared query parameters detected during a dry run validation.",
    )
    vectorSearchStatistics: Optional[VectorSearchStatistics] = Field(
        None, description="Output only. Vector Search query specific statistics."
    )


class ListModelsResponse(BaseModel):
    models: Optional[List[Model]] = Field(
        None,
        description="Models in the requested dataset. Only the following fields are populated: model_reference, model_type, creation_time, last_modified_time and labels.",
    )
    nextPageToken: Optional[str] = Field(
        None, description="A token to request the next page of results."
    )


class ListRoutinesResponse(BaseModel):
    nextPageToken: Optional[str] = Field(
        None, description="A token to request the next page of results."
    )
    routines: Optional[List[Routine]] = Field(
        None,
        description="Routines in the requested dataset. Unless read_mask is set in the request, only the following fields are populated: etag, project_id, dataset_id, routine_id, routine_type, creation_time, last_modified_time, language, and remote_function_options.",
    )


class Model(BaseModel):
    bestTrialId: Optional[str] = Field(
        None, description="The best trial_id across all training runs."
    )
    creationTime: Optional[str] = Field(
        None,
        description="Output only. The time when this model was created, in millisecs since the epoch.",
    )
    defaultTrialId: Optional[str] = Field(
        None,
        description="Output only. The default trial_id to use in TVFs when the trial_id is not passed in. For single-objective [hyperparameter tuning](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview) models, this is the best trial ID. For multi-objective [hyperparameter tuning](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview) models, this is the smallest trial ID among all Pareto optimal trials.",
    )
    description: Optional[str] = Field(
        None, description="Optional. A user-friendly description of this model."
    )
    encryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None,
        description="Custom encryption configuration (e.g., Cloud KMS keys). This shows the encryption configuration of the model data while stored in BigQuery storage. This field can be used with PatchModel to update encryption key for an already encrypted model.",
    )
    etag: Optional[str] = Field(
        None, description="Output only. A hash of this resource."
    )
    expirationTime: Optional[str] = Field(
        None,
        description="Optional. The time when this model expires, in milliseconds since the epoch. If not present, the model will persist indefinitely. Expired models will be deleted and their storage reclaimed. The defaultTableExpirationMs property of the encapsulating dataset can be used to set a default expirationTime on newly created models.",
    )
    featureColumns: Optional[List[StandardSqlField]] = Field(
        None,
        description="Output only. Input feature columns for the model inference. If the model is trained with TRANSFORM clause, these are the input of the TRANSFORM clause.",
    )
    friendlyName: Optional[str] = Field(
        None, description="Optional. A descriptive name for this model."
    )
    hparamSearchSpaces: Optional[HparamSearchSpaces] = Field(
        None, description="Output only. All hyperparameter search spaces in this model."
    )
    hparamTrials: Optional[List[HparamTuningTrial]] = Field(
        None,
        description="Output only. Trials of a [hyperparameter tuning](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview) model sorted by trial_id.",
    )
    labelColumns: Optional[List[StandardSqlField]] = Field(
        None,
        description='Output only. Label columns that were used to train this model. The output of the model will have a "predicted_" prefix to these columns.',
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="The labels associated with this model. You can use these to organize and group your models. Label keys and values can be no longer than 63 characters, can only contain lowercase letters, numeric characters, underscores and dashes. International characters are allowed. Label values are optional. Label keys must start with a letter and each label in the list must have a different key.",
    )
    lastModifiedTime: Optional[str] = Field(
        None,
        description="Output only. The time when this model was last modified, in millisecs since the epoch.",
    )
    location: Optional[str] = Field(
        None,
        description="Output only. The geographic location where the model resides. This value is inherited from the dataset.",
    )
    modelReference: Optional[ModelReference] = Field(
        None, description="Required. Unique identifier for this model."
    )
    modelType: Optional[ModelType] = Field(
        None, description="Output only. Type of the model resource."
    )
    optimalTrialIds: Optional[List[str]] = Field(
        None,
        description="Output only. For single-objective [hyperparameter tuning](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview) models, it only contains the best trial. For multi-objective [hyperparameter tuning](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-hp-tuning-overview) models, it contains all Pareto optimal trials sorted by trial_id.",
    )
    remoteModelInfo: Optional[RemoteModelInfo] = Field(
        None, description="Output only. Remote model info"
    )
    trainingRuns: Optional[List[TrainingRun]] = Field(
        None,
        description="Information for all training runs in increasing order of start_time.",
    )
    transformColumns: Optional[List[TransformColumn]] = Field(
        None,
        description="Output only. This field will be populated if a TRANSFORM clause was used to train a model. TRANSFORM clause (if used) takes feature_columns as input and outputs transform_columns. transform_columns then are used to train the model.",
    )


class QueryParameter(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Optional. If unset, this is a positional parameter. Otherwise, should be unique within a query.",
    )
    parameterType: Optional[QueryParameterType] = Field(
        None, description="Required. The type of this parameter."
    )
    parameterValue: Optional[QueryParameterValue] = Field(
        None, description="Required. The value of this parameter."
    )


class StructType(BaseModel):
    description: Optional[str] = Field(
        None, description="Optional. Human-oriented description of the field."
    )
    name: Optional[str] = Field(None, description="Optional. The name of this field.")
    type: Optional[QueryParameterType] = Field(
        None, description="Required. The type of this field."
    )


class QueryParameterType(BaseModel):
    arrayType: Optional[QueryParameterType] = Field(
        None,
        description="Optional. The type of the array's elements, if this is an array.",
    )
    rangeElementType: Optional[QueryParameterType] = Field(
        None, description="Optional. The element type of the range, if this is a range."
    )
    structTypes: Optional[List[StructType]] = Field(
        None,
        description="Optional. The types of the fields of this struct, in order, if this is a struct.",
    )
    type: Optional[str] = Field(
        None, description="Required. The top level type of this field."
    )


class QueryParameterValue(BaseModel):
    arrayValues: Optional[List[QueryParameterValue]] = Field(
        None, description="Optional. The array values, if this is an array type."
    )
    rangeValue: Optional[RangeValue] = Field(
        None, description="Optional. The range value, if this is a range type."
    )
    structValues: Optional[Dict[str, QueryParameterValue]] = Field(
        None, description="The struct field values."
    )
    value: Optional[Any] = Field(
        None, description="Optional. The value of this value, if a simple scalar type."
    )


class RangeValue(BaseModel):
    end: Optional[QueryParameterValue] = Field(
        None,
        description="Optional. The end value of the range. A missing value represents an unbounded end.",
    )
    start: Optional[QueryParameterValue] = Field(
        None,
        description="Optional. The start value of the range. A missing value represents an unbounded start.",
    )


class QueryRequest(BaseModel):
    connectionProperties: Optional[List[ConnectionProperty]] = Field(
        None,
        description="Optional. Connection properties which can modify the query behavior.",
    )
    continuous: Optional[bool] = Field(
        None,
        description="[Optional] Specifies whether the query should be executed as a continuous query. The default value is false.",
    )
    createSession: Optional[bool] = Field(
        None,
        description="Optional. If true, creates a new session using a randomly generated session_id. If false, runs query with an existing session_id passed in ConnectionProperty, otherwise runs query in non-session mode. The session location will be set to QueryRequest.location if it is present, otherwise it's set to the default location based on existing routing logic.",
    )
    defaultDataset: Optional[DatasetReference] = Field(
        None,
        description="Optional. Specifies the default datasetId and projectId to assume for any unqualified table names in the query. If not set, all table names in the query string must be qualified in the format 'datasetId.tableId'.",
    )
    destinationEncryptionConfiguration: Optional[EncryptionConfiguration] = Field(
        None,
        description="Optional. Custom encryption configuration (e.g., Cloud KMS keys)",
    )
    dryRun: Optional[bool] = Field(
        None,
        description="Optional. If set to true, BigQuery doesn't run the job. Instead, if the query is valid, BigQuery returns statistics about the job such as how many bytes would be processed. If the query is invalid, an error returns. The default value is false.",
    )
    formatOptions: Optional[DataFormatOptions] = Field(
        None, description="Optional. Output format adjustments."
    )
    jobCreationMode: Optional[JobCreationMode] = Field(
        None,
        description="Optional. If not set, jobs are always required. If set, the query request will follow the behavior described JobCreationMode. [Preview](https://cloud.google.com/products/#product-launch-stages)",
    )
    jobTimeoutMs: Optional[str] = Field(
        None,
        description="Optional. Job timeout in milliseconds. If this time limit is exceeded, BigQuery will attempt to stop a longer job, but may not always succeed in canceling it before the job completes. For example, a job that takes more than 60 seconds to complete has a better chance of being stopped than a job that takes 10 seconds to complete. This timeout applies to the query even if a job does not need to be created.",
    )
    kind: Optional[str] = Field(
        "bigquery#queryRequest", description="The resource type of the request."
    )
    labels: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional. The labels associated with this query. Labels can be used to organize and group query jobs. Label keys and values can be no longer than 63 characters, can only contain lowercase letters, numeric characters, underscores and dashes. International characters are allowed. Label keys must start with a letter and each label in the list must have a different key.",
    )
    location: Optional[str] = Field(
        None,
        description="The geographic location where the job should run. For more information, see how to [specify locations](https://cloud.google.com/bigquery/docs/locations#specify_locations).",
    )
    maxResults: Optional[int] = Field(
        None,
        description="Optional. The maximum number of rows of data to return per page of results. Setting this flag to a small value such as 1000 and then paging through results might improve reliability when the query result set is large. In addition to this limit, responses are also limited to 10 MB. By default, there is no maximum row count, and only the byte limit applies.",
    )
    maximumBytesBilled: Optional[str] = Field(
        None,
        description="Optional. Limits the bytes billed for this query. Queries with bytes billed above this limit will fail (without incurring a charge). If unspecified, the project default is used.",
    )
    parameterMode: Optional[str] = Field(
        None,
        description="GoogleSQL only. Set to POSITIONAL to use positional (?) query parameters or to NAMED to use named (@myparam) query parameters in this query.",
    )
    preserveNulls: Optional[bool] = Field(
        None, description="This property is deprecated."
    )
    query: Optional[str] = Field(
        None,
        description='Required. A query string to execute, using Google Standard SQL or legacy SQL syntax. Example: "SELECT COUNT(f1) FROM myProjectId.myDatasetId.myTableId".',
    )
    queryParameters: Optional[List[QueryParameter]] = Field(
        None, description="Query parameters for GoogleSQL queries."
    )
    requestId: Optional[str] = Field(
        None,
        description="Optional. A unique user provided identifier to ensure idempotent behavior for queries. Note that this is different from the job_id. It has the following properties: 1. It is case-sensitive, limited to up to 36 ASCII characters. A UUID is recommended. 2. Read only queries can ignore this token since they are nullipotent by definition. 3. For the purposes of idempotency ensured by the request_id, a request is considered duplicate of another only if they have the same request_id and are actually duplicates. When determining whether a request is a duplicate of another request, all parameters in the request that may affect the result are considered. For example, query, connection_properties, query_parameters, use_legacy_sql are parameters that affect the result and are considered when determining whether a request is a duplicate, but properties like timeout_ms don't affect the result and are thus not considered. Dry run query requests are never considered duplicate of another request. 4. When a duplicate mutating query request is detected, it returns: a. the results of the mutation if it completes successfully within the timeout. b. the running operation if it is still in progress at the end of the timeout. 5. Its lifetime is limited to 15 minutes. In other words, if two requests are sent with the same request_id, but more than 15 minutes apart, idempotency is not guaranteed.",
    )
    reservation: Optional[str] = Field(
        None,
        description="Optional. The reservation that jobs.query request would use. User can specify a reservation to execute the job.query. The expected format is `projects/{project}/locations/{location}/reservations/{reservation}`.",
    )
    timeoutMs: Optional[int] = Field(
        None,
        description="Optional. Optional: Specifies the maximum amount of time, in milliseconds, that the client is willing to wait for the query to complete. By default, this limit is 10 seconds (10,000 milliseconds). If the query is complete, the jobComplete field in the response is true. If the query has not yet completed, jobComplete is false. You can request a longer timeout period in the timeoutMs field. However, the call is not guaranteed to wait for the specified timeout; it typically returns after around 200 seconds (200,000 milliseconds), even if the query is not complete. If jobComplete is false, you can continue to wait for the query to complete by calling the getQueryResults method until the jobComplete field in the getQueryResults response is true.",
    )
    useLegacySql: Optional[bool] = Field(
        True,
        description="Specifies whether to use BigQuery's legacy SQL dialect for this query. The default value is true. If set to false, the query will use BigQuery's GoogleSQL: https://cloud.google.com/bigquery/sql-reference/ When useLegacySql is set to false, the value of flattenResults is ignored; query will be run as if flattenResults is false.",
    )
    useQueryCache: Optional[bool] = Field(
        True,
        description="Optional. Whether to look for the result in the query cache. The query cache is a best-effort cache that will be flushed whenever tables in the query are modified. The default value is true.",
    )
    writeIncrementalResults: Optional[bool] = Field(
        None,
        description="Optional. This is only supported for SELECT query. If set, the query is allowed to write results incrementally to the temporary result table. This may incur a performance penalty. This option cannot be used with Legacy SQL. This feature is not yet available.",
    )

    def to_job_configuration(self) -> JobConfiguration:
        return JobConfiguration(
            dryRun=self.dryRun,
            jobTimeoutMs=self.jobTimeoutMs,
            jobType="QUERY",
            labels=self.labels,
            query=JobConfigurationQuery(
                connectionProperties=self.connectionProperties,
                continuous=self.continuous,
                createSession=self.createSession,
                defaultDataset=self.defaultDataset,
                destinationEncryptionConfiguration=self.destinationEncryptionConfiguration,
                maximumBytesBilled=self.maximumBytesBilled,
                parameterMode=self.parameterMode,
                preserveNulls=self.preserveNulls,
                query=self.query,
                queryParameters=self.queryParameters,
                useLegacySql=self.useLegacySql,
                useQueryCache=self.useQueryCache,
                writeIncrementalResults=self.writeIncrementalResults,
            ),
            reservation=self.reservation,
        )


class Routine(BaseModel):
    arguments: Optional[List[Argument]] = Field(None, description="Optional.")
    creationTime: Optional[str] = Field(
        None,
        description="Output only. The time when this routine was created, in milliseconds since the epoch.",
    )
    dataGovernanceType: Optional[DataGovernanceType] = Field(
        None,
        description="Optional. If set to `DATA_MASKING`, the function is validated and made available as a masking function. For more information, see [Create custom masking routines](https://cloud.google.com/bigquery/docs/user-defined-functions#custom-mask).",
    )
    definitionBody: Optional[str] = Field(
        None,
        description='Required. The body of the routine. For functions, this is the expression in the AS clause. If language=SQL, it is the substring inside (but excluding) the parentheses. For example, for the function created with the following statement: `CREATE FUNCTION JoinLines(x string, y string) as (concat(x, "\\n", y))` The definition_body is `concat(x, "\\n", y)` (\\n is not replaced with linebreak). If language=JAVASCRIPT, it is the evaluated string in the AS clause. For example, for the function created with the following statement: `CREATE FUNCTION f() RETURNS STRING LANGUAGE js AS \'return "\\n";\\n\'` The definition_body is `return "\\n";\\n` Note that both \\n are replaced with linebreaks.',
    )
    description: Optional[str] = Field(
        None, description="Optional. The description of the routine, if defined."
    )
    determinismLevel: Optional[DeterminismLevel] = Field(
        None,
        description="Optional. The determinism level of the JavaScript UDF, if defined.",
    )
    etag: Optional[str] = Field(
        None, description="Output only. A hash of this resource."
    )
    importedLibraries: Optional[List[str]] = Field(
        None,
        description='Optional. If language = "JAVASCRIPT", this field stores the path of the imported JAVASCRIPT libraries.',
    )
    language: Optional[Language] = Field(
        None,
        description='Optional. Defaults to "SQL" if remote_function_options field is absent, not set otherwise.',
    )
    lastModifiedTime: Optional[str] = Field(
        None,
        description="Output only. The time when this routine was last modified, in milliseconds since the epoch.",
    )
    remoteFunctionOptions: Optional[RemoteFunctionOptions] = Field(
        None, description="Optional. Remote function specific options."
    )
    returnTableType: Optional[StandardSqlTableType] = Field(
        None,
        description='Optional. Can be set only if routine_type = "TABLE_VALUED_FUNCTION". If absent, the return table type is inferred from definition_body at query time in each query that references this routine. If present, then the columns in the evaluated table result will be cast to match the column types specified in return table type, at query time.',
    )
    returnType: Optional[StandardSqlDataType] = Field(
        None,
        description='Optional if language = "SQL"; required otherwise. Cannot be set if routine_type = "TABLE_VALUED_FUNCTION". If absent, the return type is inferred from definition_body at query time in each query that references this routine. If present, then the evaluated result will be cast to the specified returned type at query time. For example, for the functions created with the following statements: * `CREATE FUNCTION Add(x FLOAT64, y FLOAT64) RETURNS FLOAT64 AS (x + y);` * `CREATE FUNCTION Increment(x FLOAT64) AS (Add(x, 1));` * `CREATE FUNCTION Decrement(x FLOAT64) RETURNS FLOAT64 AS (Add(x, -1));` The return_type is `{type_kind: "FLOAT64"}` for `Add` and `Decrement`, and is absent for `Increment` (inferred as FLOAT64 at query time). Suppose the function `Add` is replaced by `CREATE OR REPLACE FUNCTION Add(x INT64, y INT64) AS (x + y);` Then the inferred return type of `Increment` is automatically changed to INT64 at query time, while the return type of `Decrement` remains FLOAT64.',
    )
    routineReference: Optional[RoutineReference] = Field(
        None, description="Required. Reference describing the ID of this routine."
    )
    routineType: Optional[RoutineType] = Field(
        None, description="Required. The type of routine."
    )
    securityMode: Optional[SecurityMode] = Field(
        None,
        description="Optional. The security mode of the routine, if defined. If not defined, the security mode is automatically determined from the routine's configuration.",
    )
    sparkOptions: Optional[SparkOptions] = Field(
        None, description="Optional. Spark specific options."
    )
    strictMode: Optional[bool] = Field(
        None,
        description="Optional. Use this option to catch many common errors. Error checking is not exhaustive, and successfully creating a procedure doesn't guarantee that the procedure will successfully execute at runtime. If `strictMode` is set to `TRUE`, the procedure body is further checked for errors such as non-existent tables or columns. The `CREATE PROCEDURE` statement fails if the body fails any of these checks. If `strictMode` is set to `FALSE`, the procedure body is checked only for syntax. For procedures that invoke themselves recursively, specify `strictMode=FALSE` to avoid non-existent procedure errors during validation. Default value is `TRUE`.",
    )


class StandardSqlDataType(BaseModel):
    arrayElementType: Optional[StandardSqlDataType] = Field(
        None, description='The type of the array\'s elements, if type_kind = "ARRAY".'
    )
    rangeElementType: Optional[StandardSqlDataType] = Field(
        None, description='The type of the range\'s elements, if type_kind = "RANGE".'
    )
    structType: Optional[StandardSqlStructType] = Field(
        None,
        description='The fields of this struct, in order, if type_kind = "STRUCT".',
    )
    typeKind: Optional[TypeKind] = Field(
        None,
        description='Required. The top level type of this field. Can be any GoogleSQL data type (e.g., "INT64", "DATE", "ARRAY").',
    )


class StandardSqlField(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Optional. The name of this field. Can be absent for struct fields.",
    )
    type: Optional[StandardSqlDataType] = Field(
        None,
        description='Optional. The type of this parameter. Absent if not explicitly specified (e.g., CREATE FUNCTION statement can omit the return type; in this case the output parameter does not have this "type" field).',
    )


class StandardSqlStructType(BaseModel):
    fields: Optional[List[StandardSqlField]] = Field(
        None, description="Fields within the struct."
    )


class StandardSqlTableType(BaseModel):
    columns: Optional[List[StandardSqlField]] = Field(
        None, description="The columns in this table type"
    )


class SystemVariables(BaseModel):
    types: Optional[Dict[str, StandardSqlDataType]] = Field(
        None, description="Output only. Data type for each system variable."
    )
    values: Optional[Dict[str, Any]] = Field(
        None, description="Output only. Value for each system variable."
    )


class TransformColumn(BaseModel):
    name: Optional[str] = Field(None, description="Output only. Name of the column.")
    transformSql: Optional[str] = Field(
        None,
        description="Output only. The SQL expression used in the column transform.",
    )
    type: Optional[StandardSqlDataType] = Field(
        None, description="Output only. Data type of the column after the transform."
    )


class CommonQueryParams(BaseModel):
    field__xgafv: Optional[FieldXgafv] = Field(None, alias="$.xgafv")
    access_token: Optional[str] = None
    alt: Optional[Alt] = Alt.json
    callback: Optional[str] = None
    fields: Optional[str] = None
    key: Optional[str] = None
    oauth_token: Optional[str] = None
    pretty_print: Optional[bool] = Field(True, alias="prettyPrint")
    quota_user: Optional[str] = Field(None, alias="quotaUser")
    upload_type: Optional[str] = Field(None, alias="uploadType")
    upload_protocol: Optional[str] = None


TableFieldSchema.model_rebuild()
Argument.model_rebuild()
Job.model_rebuild()
JobConfiguration.model_rebuild()
JobConfigurationQuery.model_rebuild()
Job1.model_rebuild()
JobStatistics.model_rebuild()
JobStatistics2.model_rebuild()
ListModelsResponse.model_rebuild()
ListRoutinesResponse.model_rebuild()
Model.model_rebuild()
QueryParameter.model_rebuild()
StructType.model_rebuild()
QueryParameterValue.model_rebuild()
Routine.model_rebuild()
StandardSqlDataType.model_rebuild()
