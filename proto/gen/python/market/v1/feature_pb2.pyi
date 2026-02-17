import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ComputedFeature(_message.Message):
    __slots__ = ("id", "bar_id", "ticker_id", "timeframe", "timestamp", "features", "feature_version", "model_id", "state_id", "state_prob", "log_likelihood", "created_at")
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    BAR_ID_FIELD_NUMBER: _ClassVar[int]
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    FEATURE_VERSION_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_PROB_FIELD_NUMBER: _ClassVar[int]
    LOG_LIKELIHOOD_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    bar_id: int
    ticker_id: int
    timeframe: str
    timestamp: _timestamp_pb2.Timestamp
    features: _containers.ScalarMap[str, float]
    feature_version: str
    model_id: str
    state_id: int
    state_prob: float
    log_likelihood: float
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., bar_id: _Optional[int] = ..., ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., features: _Optional[_Mapping[str, float]] = ..., feature_version: _Optional[str] = ..., model_id: _Optional[str] = ..., state_id: _Optional[int] = ..., state_prob: _Optional[float] = ..., log_likelihood: _Optional[float] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetFeaturesRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe", "start", "end", "page_size", "page_token")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    start: _timestamp_pb2.Timestamp
    end: _timestamp_pb2.Timestamp
    page_size: int
    page_token: str
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class GetFeaturesResponse(_message.Message):
    __slots__ = ("features", "next_page_token", "total_count")
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    features: _containers.RepeatedCompositeFieldContainer[ComputedFeature]
    next_page_token: str
    total_count: int
    def __init__(self, features: _Optional[_Iterable[_Union[ComputedFeature, _Mapping]]] = ..., next_page_token: _Optional[str] = ..., total_count: _Optional[int] = ...) -> None: ...

class GetExistingFeatureBarIdsRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe", "start", "end")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    start: _timestamp_pb2.Timestamp
    end: _timestamp_pb2.Timestamp
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetExistingFeatureBarIdsResponse(_message.Message):
    __slots__ = ("bar_ids",)
    BAR_IDS_FIELD_NUMBER: _ClassVar[int]
    bar_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, bar_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class BulkUpsertFeaturesRequest(_message.Message):
    __slots__ = ("features",)
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    features: _containers.RepeatedCompositeFieldContainer[ComputedFeature]
    def __init__(self, features: _Optional[_Iterable[_Union[ComputedFeature, _Mapping]]] = ...) -> None: ...

class BulkUpsertFeaturesResponse(_message.Message):
    __slots__ = ("rows_upserted",)
    ROWS_UPSERTED_FIELD_NUMBER: _ClassVar[int]
    rows_upserted: int
    def __init__(self, rows_upserted: _Optional[int] = ...) -> None: ...

class StoreStatesRequest(_message.Message):
    __slots__ = ("states", "model_id")
    STATES_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    states: _containers.RepeatedCompositeFieldContainer[ComputedFeature]
    model_id: str
    def __init__(self, states: _Optional[_Iterable[_Union[ComputedFeature, _Mapping]]] = ..., model_id: _Optional[str] = ...) -> None: ...

class StoreStatesResponse(_message.Message):
    __slots__ = ("rows_stored",)
    ROWS_STORED_FIELD_NUMBER: _ClassVar[int]
    rows_stored: int
    def __init__(self, rows_stored: _Optional[int] = ...) -> None: ...

class GetStatesRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe", "model_id", "start", "end")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    model_id: str
    start: _timestamp_pb2.Timestamp
    end: _timestamp_pb2.Timestamp
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., model_id: _Optional[str] = ..., start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetStatesResponse(_message.Message):
    __slots__ = ("states",)
    STATES_FIELD_NUMBER: _ClassVar[int]
    states: _containers.RepeatedCompositeFieldContainer[ComputedFeature]
    def __init__(self, states: _Optional[_Iterable[_Union[ComputedFeature, _Mapping]]] = ...) -> None: ...

class GetLatestStatesRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ...) -> None: ...

class GetLatestStatesResponse(_message.Message):
    __slots__ = ("states",)
    STATES_FIELD_NUMBER: _ClassVar[int]
    states: _containers.RepeatedCompositeFieldContainer[ComputedFeature]
    def __init__(self, states: _Optional[_Iterable[_Union[ComputedFeature, _Mapping]]] = ...) -> None: ...
