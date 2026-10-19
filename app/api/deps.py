from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock, SystemClock
from app.config import Settings, get_settings
from app.services.trades import TradeService


def get_clock(request: Request) -> Clock:
    clock = getattr(request.app.state, "clock", None)
    if clock is not None:
        return clock
    return SystemClock(request.app.state.settings.business_timezone)


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_trade_service(
    request: Request,
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
) -> TradeService:
    bulk_max = getattr(request.app.state, "bulk_max_items", settings.bulk_max_items)
    return TradeService(clock, session_factory, bulk_max)
