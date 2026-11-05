"""Bounded review inputs. Caller-provided evidence is not authenticated account data."""
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from .coaching import Input, Number

Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")]
Text = Annotated[str, Field(min_length=1, max_length=500)]
Quantity = Annotated[Number, Field(ge=0, le=1_000_000)]
Template = Literal["daily_logs", "workout_preparation", "weekly_review"]
Source = Literal["nutrition", "strength", "activities", "lifestyle", "sleep", "hydration", "measurements", "recovery", "plan"]


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamp requires an explicit UTC offset")
    return result


class SourceCoverage(Input):
    source: Source
    status: Literal["available", "partial", "unavailable", "not_configured"]
    fetched_at: str | None = None
    reason: Literal["AUTH_REQUIRED", "ACCESS_DENIED", "RATE_LIMITED", "NETWORK_ERROR", "TIMEOUT", "STALE", "TRUNCATED", "UNSUPPORTED", "NOT_CONNECTED", "NO_DATA", "UNKNOWN"] | None = None

    @model_validator(mode="after")
    def check(self):
        if self.fetched_at is not None:
            timestamp(self.fetched_at)
        if self.status in {"partial", "unavailable"} and self.reason is None:
            raise ValueError("Unavailable/partial sources require a reason")
        if self.status == "available" and (self.fetched_at is None or self.reason is not None):
            raise ValueError("Available sources require a fetch timestamp and no failure reason")
        return self


class Diary(Input):
    complete: StrictBool | None = None
    calories_kcal: Quantity | None = None
    goal_kcal: Quantity | None = None
    protein_g: Quantity | None = None
    carbohydrate_g: Quantity | None = None
    fat_g: Quantity | None = None
    # Exact source entry IDs are needed for duplicate/correction discussions.
    missing_expected_meals: list[Text] = Field(default_factory=list, max_length=10)
    possible_duplicate_entry_ids: list[Identifier] = Field(default_factory=list, max_length=20)


class Routine(Input):
    routine_id: Identifier
    label: Text
    confirmed: StrictBool
    expected: StrictBool = True
    weekdays: list[Annotated[StrictInt, Field(ge=0, le=6)]] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    expected_amount: Quantity | None = None
    unit: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    recorded: Literal["present", "skipped", "missing", "unknown"] = "unknown"
    amount: Quantity | None = None

    @model_validator(mode="after")
    def units(self):
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("Duplicate routine weekdays")
        if (self.expected_amount is not None or self.amount is not None) and self.unit is None:
            raise ValueError("Routine quantities require confirmed units")
        if self.recorded != "present" and self.amount is not None:
            raise ValueError("An amount requires a present record")
        return self


class ReviewSet(Input):
    activity_id: Identifier
    set_id: Identifier
    exercise_id: Identifier | None = None
    equipment: Identifier | None = None
    reps: Annotated[StrictInt, Field(ge=0, le=1000)] | None = None
    load: Quantity | None = None
    load_unit: Literal["kg", "lb", "garmin_raw_unverified", "unknown"] = "unknown"
    kind: Literal["work", "warmup", "drop", "unknown"] = "unknown"
    # Only compare sets the caller has established use the same convention.
    comparison_group: Identifier | None = None
    intentional_variation: StrictBool = False


class RecordGap(Input):
    source: Literal["activities", "sleep", "hydration", "measurements"]
    record_id: Identifier
    kind: Literal["missing_expected", "possible_duplicate", "inconsistent", "unknown_units"]
    evidence: Text


class LogReview(Input):
    calendar_date: str
    timezone: str
    as_of: str
    coverage: list[SourceCoverage] = Field(min_length=1, max_length=9)
    diary: Diary | None = None
    routines: list[Routine] = Field(default_factory=list, max_length=50)
    sets: list[ReviewSet] = Field(default_factory=list, max_length=500)
    gaps: list[RecordGap] = Field(default_factory=list, max_length=50)
    calorie_goal_ratio: Annotated[Number, Field(ge=0.1, le=0.9)] = 0.7
    weight_outlier_ratio: Annotated[Number, Field(ge=0.1, le=1)] = 0.25

    @model_validator(mode="after")
    def aligned(self):
        target = date.fromisoformat(self.calendar_date)
        now = timestamp(self.as_of)
        if target >= now.astimezone(ZoneInfo(self.timezone)).date():
            raise ValueError("Log review requires a completed local calendar day")
        if (now.astimezone(ZoneInfo(self.timezone)).date() - target).days > 31:
            raise ValueError("Log review supports the previous 31 days")
        if len({v.source for v in self.coverage}) != len(self.coverage):
            raise ValueError("Duplicate source coverage")
        if any(v.fetched_at and timestamp(v.fetched_at) > now for v in self.coverage):
            raise ValueError("Fetch timestamps cannot be in the future")
        if len({v.routine_id for v in self.routines}) != len(self.routines):
            raise ValueError("Duplicate routine IDs")
        if len({(v.activity_id, v.set_id) for v in self.sets}) != len(self.sets):
            raise ValueError("Duplicate set IDs within an activity")
        supplied = {"nutrition": self.diary is not None, "strength": bool(self.sets), "lifestyle": bool(self.routines)}
        coverage = {v.source: v.status for v in self.coverage}
        for source, present in supplied.items():
            if present and coverage.get(source) not in {"available", "partial"}:
                raise ValueError("Evidence requires available or partial source coverage")
        if any(coverage.get(g.source) not in {"available", "partial"} for g in self.gaps):
            raise ValueError("Record gaps require source coverage")
        return self


def default_sources() -> list[Source]:
    return ["activities", "nutrition", "lifestyle", "sleep", "strength", "recovery", "plan"]


class ReviewSchedule(Input):
    schedule_id: Identifier
    template: Template
    timezone: str
    local_time: Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
    start_date: str
    frequency: Literal["daily", "weekly"] = "daily"
    interval: Annotated[StrictInt, Field(ge=1, le=30)] = 1
    weekdays: list[Annotated[StrictInt, Field(ge=0, le=6)]] = Field(default_factory=list, max_length=7)
    enabled: StrictBool = True
    sources: list[Source] = Field(default_factory=default_sources, min_length=1, max_length=9)
    start_grace_minutes: Annotated[StrictInt, Field(ge=5, le=120)] = 15
    deadline_minutes: Annotated[StrictInt, Field(ge=5, le=120)] = 15
    delivery_grace_minutes: Annotated[StrictInt, Field(ge=1, le=120)] = 15

    @model_validator(mode="after")
    def valid(self):
        ZoneInfo(self.timezone)
        date.fromisoformat(self.start_date)
        if self.frequency == "weekly" and not self.weekdays:
            raise ValueError("Weekly schedules require weekdays (Monday=0)")
        if self.frequency == "daily" and self.weekdays:
            raise ValueError("Daily schedules use interval; weekdays require weekly frequency")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("Duplicate weekdays")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("Duplicate configured sources")
        return self


class Finding(Input):
    finding_id: Identifier
    calendar_date: str
    source: Source
    rule: Identifier
    target_id: Identifier
    evidence: Text
    question: Text
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("calendar_date")
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value
