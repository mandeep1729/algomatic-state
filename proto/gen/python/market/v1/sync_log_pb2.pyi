import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DataSyncLog(_message.Message):
    __slots__ = ("id", "ticker_id", "timeframe", "last_synced_timestamp", "first_synced_timestamp", "last_sync_at", "bars_fetched", "total_bars", "status", "error_message")
    ID_FIELD_NUMBER: _ClassVar[int]
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    LAST_SYNCED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    FIRST_SYNCED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LAST_SYNC_AT_FIELD_NUMBER: _ClassVar[int]
    BARS_FETCHED_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BARS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    id: int
    ticker_id: int
    timeframe: str
    last_synced_timestamp: _timestamp_pb2.Timestamp
    first_synced_timestamp: _timestamp_pb2.Timestamp
    last_sync_at: _timestamp_pb2.Timestamp
    bars_fetched: int
    total_bars: int
    status: str
    error_message: str
    def __init__(self, id: _Optional[int] = ..., ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., last_synced_timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., first_synced_timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., last_sync_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bars_fetched: _Optional[int] = ..., total_bars: _Optional[int] = ..., status: _Optional[str] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetSyncLogRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ...) -> None: ...

class GetSyncLogResponse(_message.Message):
    __slots__ = ("sync_log",)
    SYNC_LOG_FIELD_NUMBER: _ClassVar[int]
    sync_log: DataSyncLog
    def __init__(self, sync_log: _Optional[_Union[DataSyncLog, _Mapping]] = ...) -> None: ...

class UpdateSyncLogRequest(_message.Message):
    __slots__ = ("ticker_id", "timeframe", "last_synced_timestamp", "first_synced_timestamp", "bars_fetched", "status", "error_message")
    TICKER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    LAST_SYNCED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    FIRST_SYNCED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BARS_FETCHED_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ticker_id: int
    timeframe: str
    last_synced_timestamp: _timestamp_pb2.Timestamp
    first_synced_timestamp: _timestamp_pb2.Timestamp
    bars_fetched: int
    status: str
    error_message: str
    def __init__(self, ticker_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., last_synced_timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., first_synced_timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bars_fetched: _Optional[int] = ..., status: _Optional[str] = ..., error_message: _Optional[str] = ...) -> None: ...

class UpdateSyncLogResponse(_message.Message):
    __slots__ = ("sync_log",)
    SYNC_LOG_FIELD_NUMBER: _ClassVar[int]
    sync_log: DataSyncLog
    def __init__(self, sync_log: _Optional[_Union[DataSyncLog, _Mapping]] = ...) -> None: ...

class ListSyncLogsRequest(_message.Message):
    __slots__ = ("symbol",)
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    def __init__(self, symbol: _Optional[str] = ...) -> None: ...

class ListSyncLogsResponse(_message.Message):
    __slots__ = ("sync_logs",)
    SYNC_LOGS_FIELD_NUMBER: _ClassVar[int]
    sync_logs: _containers.RepeatedCompositeFieldContainer[DataSyncLog]
    def __init__(self, sync_logs: _Optional[_Iterable[_Union[DataSyncLog, _Mapping]]] = ...) -> None: ...
