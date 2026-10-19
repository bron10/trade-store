from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.deps import get_trade_service
from app.domain import ApplyOutcome
from app.schemas.trade import (
    IDENTIFIER_PATTERN,
    BulkItemResult,
    BulkRequest,
    BulkResponse,
    ErrorResponse,
    TradeCreate,
    TradePage,
    TradeRead,
)
from app.services.trades import TradeService

router = APIRouter(tags=["trades"])

TradeId = Annotated[str, Path(min_length=1, max_length=64, pattern=IDENTIFIER_PATTERN)]

_ERROR_RESPONSES = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@router.post(
    "/trades",
    response_model=TradeRead,
    status_code=201,
    responses={200: {"model": TradeRead}, **_ERROR_RESPONSES},
    summary="Insert a trade or replace it when the incoming version is equal or higher",
)
def create_trade(
    payload: TradeCreate,
    response: Response,
    service: TradeService = Depends(get_trade_service),
) -> TradeRead:
    outcome, stored = service.ingest(payload.to_domain())
    response.status_code = 201 if outcome is ApplyOutcome.CREATED else 200
    return TradeRead.from_stored(stored)


@router.post(
    "/trades/bulk",
    response_model=BulkResponse,
    responses={200: {"model": BulkResponse}, 207: {"model": BulkResponse}, **_ERROR_RESPONSES},
    summary="Ingest a batch of trades and return one result per input item",
)
def create_trades_bulk(
    payload: BulkRequest,
    response: Response,
    service: TradeService = Depends(get_trade_service),
) -> BulkResponse:
    results = service.ingest_many(payload.trades)
    response.status_code = 200 if all(item.status_code < 400 for item in results) else 207
    return BulkResponse(results=[BulkItemResult.from_item(item) for item in results])


@router.get(
    "/trades/{trade_id}",
    response_model=TradeRead,
    responses=_ERROR_RESPONSES,
    summary="Return the current trade",
)
def get_trade(
    trade_id: TradeId,
    service: TradeService = Depends(get_trade_service),
) -> TradeRead:
    return TradeRead.from_stored(service.get_trade(trade_id))


@router.get(
    "/trades",
    response_model=TradePage,
    responses=_ERROR_RESPONSES,
    summary="List current trades",
)
def list_trades(
    service: TradeService = Depends(get_trade_service),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
) -> TradePage:
    items, total = service.list_trades(limit=limit, offset=offset)
    return TradePage(
        items=[TradeRead.from_stored(item) for item in items],
        limit=limit,
        offset=offset,
        total=total,
    )
