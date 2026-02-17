import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Ticker(_message.Message):
    __slots__ = ("id", "symbol", "name", "exchange", "asset_type", "is_active", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_FIELD_NUMBER: _ClassVar[int]
    ASSET_TYPE_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    symbol: str
    name: str
    exchange: str
    asset_type: str
    is_active: bool
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., symbol: _Optional[str] = ..., name: _Optional[str] = ..., exchange: _Optional[str] = ..., asset_type: _Optional[str] = ..., is_active: bool = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetTickerRequest(_message.Message):
    __slots__ = ("symbol",)
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    def __init__(self, symbol: _Optional[str] = ...) -> None: ...

class GetTickerResponse(_message.Message):
    __slots__ = ("ticker",)
    TICKER_FIELD_NUMBER: _ClassVar[int]
    ticker: Ticker
    def __init__(self, ticker: _Optional[_Union[Ticker, _Mapping]] = ...) -> None: ...

class ListTickersRequest(_message.Message):
    __slots__ = ("active_only",)
    ACTIVE_ONLY_FIELD_NUMBER: _ClassVar[int]
    active_only: bool
    def __init__(self, active_only: bool = ...) -> None: ...

class ListTickersResponse(_message.Message):
    __slots__ = ("tickers",)
    TICKERS_FIELD_NUMBER: _ClassVar[int]
    tickers: _containers.RepeatedCompositeFieldContainer[Ticker]
    def __init__(self, tickers: _Optional[_Iterable[_Union[Ticker, _Mapping]]] = ...) -> None: ...

class GetOrCreateTickerRequest(_message.Message):
    __slots__ = ("symbol", "name", "exchange", "asset_type")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_FIELD_NUMBER: _ClassVar[int]
    ASSET_TYPE_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    name: str
    exchange: str
    asset_type: str
    def __init__(self, symbol: _Optional[str] = ..., name: _Optional[str] = ..., exchange: _Optional[str] = ..., asset_type: _Optional[str] = ...) -> None: ...

class GetOrCreateTickerResponse(_message.Message):
    __slots__ = ("ticker", "created")
    TICKER_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    ticker: Ticker
    created: bool
    def __init__(self, ticker: _Optional[_Union[Ticker, _Mapping]] = ..., created: bool = ...) -> None: ...

class BulkUpsertTickersRequest(_message.Message):
    __slots__ = ("tickers",)
    TICKERS_FIELD_NUMBER: _ClassVar[int]
    tickers: _containers.RepeatedCompositeFieldContainer[Ticker]
    def __init__(self, tickers: _Optional[_Iterable[_Union[Ticker, _Mapping]]] = ...) -> None: ...

class BulkUpsertTickersResponse(_message.Message):
    __slots__ = ("upserted_count",)
    UPSERTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    upserted_count: int
    def __init__(self, upserted_count: _Optional[int] = ...) -> None: ...
