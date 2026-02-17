import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OHLCVBar(_message.Message):
    __slots__ = ("id", "ticker_id", "timeframe", "timestamp", "open", "high", "low", "close", "volume", "trade_count", "source", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    TRADE_COUNT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    ticker_id: int
    timeframe: str
    timestamp: _timestamp_pb2.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_count: int
    source: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., open: _Optional[float] = ..., high: _Optional[float] = ..., low: _Optional[float] = ..., close: _Optional[float] = ..., volume: _Optional[int] = ..., trade_count: _Optional[int] = ..., source: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetBarsRequest(_message.Message):
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

class GetBarsResponse(_message.Message):
    __slots__ = ("bars", "next_page_token", "total_count")
    BARS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    bars: _containers.RepeatedCompositeFieldContainer[OHLCVBar]
    next_page_token: str
    total_count: int
    def __init__(self, bars: _Optional[_Iterable[_Union[OHLCVBar, _Mapping]]] = ..., next_page_token: _Optional[str] = ..., total_count: _Optional[int] = ...) -> None: ...

class StreamBarsRequest(_message.Message):
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

class BulkInsertBarsRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe", "source", "bars")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    BARS_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    source: str
    bars: _containers.RepeatedCompositeFieldContainer[OHLCVBar]
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., source: _Optional[str] = ..., bars: _Optional[_Iterable[_Union[OHLCVBar, _Mapping]]] = ...) -> None: ...

class BulkInsertBarsResponse(_message.Message):
    __slots__ = ("rows_inserted",)
    ROWS_INSERTED_FIELD_NUMBER: _ClassVar[int]
    rows_inserted: int
    def __init__(self, rows_inserted: _Optional[int] = ...) -> None: ...

class DeleteBarsRequest(_message.Message):
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

class DeleteBarsResponse(_message.Message):
    __slots__ = ("rows_deleted",)
    ROWS_DELETED_FIELD_NUMBER: _ClassVar[int]
    rows_deleted: int
    def __init__(self, rows_deleted: _Optional[int] = ...) -> None: ...

class GetLatestTimestampRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ...) -> None: ...

class GetLatestTimestampResponse(_message.Message):
    __slots__ = ("timestamp",)
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetEarliestTimestampRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ...) -> None: ...

class GetEarliestTimestampResponse(_message.Message):
    __slots__ = ("timestamp",)
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetBarCountRequest(_message.Message):
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

class GetBarCountResponse(_message.Message):
    __slots__ = ("count",)
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...

class GetBarIdsForTimestampsRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe", "timestamps")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMPS_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    timestamps: _containers.RepeatedCompositeFieldContainer[_timestamp_pb2.Timestamp]
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., timestamps: _Optional[_Iterable[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]]] = ...) -> None: ...

class GetBarIdsForTimestampsResponse(_message.Message):
    __slots__ = ("timestamp_to_id",)
    class TimestampToIdEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    TIMESTAMP_TO_ID_FIELD_NUMBER: _ClassVar[int]
    timestamp_to_id: _containers.ScalarMap[str, int]
    def __init__(self, timestamp_to_id: _Optional[_Mapping[str, int]] = ...) -> None: ...
