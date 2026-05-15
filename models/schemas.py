from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TripQuery(BaseModel):
    origin: str
    destination: str
    check_in: date
    check_out: date
    num_people: int = Field(ge=1)
    budget_eur: Optional[float] = None
    confirmed: bool = False  # True only when user has confirmed all details


class Flight(BaseModel):
    airline: str
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration: Optional[str] = None
    price_eur: float
    stops: int = 0


class FlightResults(BaseModel):
    flights: list[Flight] = Field(default_factory=list)


class Hotel(BaseModel):
    name: str
    price_per_night_eur: float
    total_price_eur: Optional[float] = None
    rating: Optional[float] = None
    free_cancellation: bool = False
    cancellation_deadline: Optional[date] = None


class HotelResults(BaseModel):
    hotels: list[Hotel] = Field(default_factory=list)


class Activity(BaseModel):
    name: str
    description: str = ""
    price_eur: Optional[float] = None
    duration: Optional[str] = None
    category: Literal["culture", "food", "outdoor", "nightlife", "shopping", "other"] = "other"


class ActivityResults(BaseModel):
    activities: list[Activity] = Field(default_factory=list)


class TripResults(BaseModel):
    query: TripQuery
    flights: list[Flight] = Field(default_factory=list)
    hotels: list[Hotel] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    summary: str = ""
