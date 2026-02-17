"""HMM-based state vector and regime tracking module."""

from src.features.state.hmm.contracts import (
    FeatureVector,
    LatentStateVector,
    HMMOutput,
    ModelMetadata,
    Timeframe,
    VALID_TIMEFRAMES,
)
from src.features.state.hmm.config import (
    StateVectorFeatureSpec,
    StateVectorConfig,
    load_feature_spec,
    create_default_config,
)
from src.features.state.hmm.artifacts import (
    ArtifactPaths,
    StatesPaths,
    get_model_path,
    get_states_path,
    generate_model_id,
    list_models,
    get_latest_model,
)
from src.features.state.hmm.scalers import (
    BaseScaler,
    RobustScaler,
    StandardScaler,
    YeoJohnsonScaler,
    CombinedScaler,
    create_scaler,
)
from src.features.state.hmm.encoders import (
    BaseEncoder,
    PCAEncoder,
    TemporalPCAEncoder,
    create_encoder,
    create_windows,
    select_latent_dim,
)
from src.features.state.hmm.hmm_model import (
    GaussianHMMWrapper,
    select_n_states,
    match_states_hungarian,
)
from src.features.state.hmm.inference import (
    InferenceEngine,
    create_inference_engine,
)
from src.features.state.hmm.data_pipeline import (
    FeatureLoader,
    GapHandler,
    TimeSplitter,
    DataSplit,
    validate_no_leakage,
    create_feature_vectors,
)
from src.features.state.hmm.training import (
    TrainingPipeline,
    TrainingConfig,
    TrainingResult,
    CrossValidator,
    HyperparameterTuner,
    HyperparameterGrid,
    train_model,
)
from src.features.state.hmm.storage import (
    StateWriter,
    StateReader,
    StateRecord,
    validate_state_dataframe,
)
from src.features.state.hmm.validation import (
    ModelValidator,
    ValidationReport,
    DwellTimeAnalyzer,
    TransitionAnalyzer,
    PosteriorAnalyzer,
    StateConditionedReturnAnalyzer,
    OODMonitor,
    generate_validation_report,
)
from src.features.state.hmm.monitoring import (
    MonitoringMetrics,
    DriftAlert,
    RetrainingTrigger,
)

__all__ = [
    # Contracts
    "FeatureVector",
    "LatentStateVector",
    "HMMOutput",
    "ModelMetadata",
    "Timeframe",
    "VALID_TIMEFRAMES",
    # Config
    "StateVectorFeatureSpec",
    "StateVectorConfig",
    "load_feature_spec",
    "create_default_config",
    # Artifacts
    "ArtifactPaths",
    "StatesPaths",
    "get_model_path",
    "get_states_path",
    "generate_model_id",
    "list_models",
    "get_latest_model",
    # Scalers
    "BaseScaler",
    "RobustScaler",
    "StandardScaler",
    "YeoJohnsonScaler",
    "CombinedScaler",
    "create_scaler",
    # Encoders
    "BaseEncoder",
    "PCAEncoder",
    "TemporalPCAEncoder",
    "create_encoder",
    "create_windows",
    "select_latent_dim",
    # HMM
    "GaussianHMMWrapper",
    "select_n_states",
    "match_states_hungarian",
    # Inference
    "InferenceEngine",
    "create_inference_engine",
    # Data Pipeline
    "FeatureLoader",
    "GapHandler",
    "TimeSplitter",
    "DataSplit",
    "validate_no_leakage",
    "create_feature_vectors",
    # Training
    "TrainingPipeline",
    "TrainingConfig",
    "TrainingResult",
    "CrossValidator",
    "HyperparameterTuner",
    "HyperparameterGrid",
    "train_model",
    # Storage
    "StateWriter",
    "StateReader",
    "StateRecord",
    "validate_state_dataframe",
    # Validation
    "ModelValidator",
    "ValidationReport",
    "DwellTimeAnalyzer",
    "TransitionAnalyzer",
    "PosteriorAnalyzer",
    "StateConditionedReturnAnalyzer",
    "OODMonitor",
    "generate_validation_report",
    # Monitoring
    "MonitoringMetrics",
    "DriftAlert",
    "RetrainingTrigger",
]
