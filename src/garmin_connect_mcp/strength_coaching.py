"""Strength exposure and sequence evidence; never estimates tissue recovery time."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator

from .coaching import Input, Number

Region = Literal["quads", "hamstrings", "glutes", "calves", "chest", "back",
                 "shoulders", "biceps", "triceps", "core", "forearms"]


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Strength timestamps require explicit timezone offsets")
    return result


class Exercise(Input):
    exercise_id: str = Field(min_length=1, max_length=100)
    equipment: str = Field(min_length=1, max_length=60)
    regions: list[Region] = Field(min_length=1, max_length=11)

    @field_validator("regions")
    @classmethod
    def distinct_regions(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Duplicate muscle regions")
        return value


class WorkSet(Exercise):
    set_id: str = Field(min_length=1, max_length=80)
    performed_at: str
    reps: Annotated[StrictInt, Field(ge=1, le=1000)]
    external_load_kg: Annotated[Number, Field(ge=0, le=2000)] | None = None
    rir: Annotated[Number, Field(ge=0, le=20)] | None = None
    warmup: bool = False

    @field_validator("performed_at")
    @classmethod
    def valid_timestamp(cls, value):
        timestamp(value)
        return value


class PlannedExercise(Exercise):
    planned_sets: Annotated[StrictInt, Field(ge=1, le=30)]
    planned_reps: Annotated[StrictInt, Field(ge=1, le=1000)]
    external_load_kg: Annotated[Number, Field(ge=0, le=2000)] | None = None


class RegionalCheck(Input):
    region: Region
    soreness: Annotated[StrictInt, Field(ge=0, le=10)] | None = None
    pain: bool | None = None


def assess_strength(as_of, recent_sets, planned_exercises, regional_check_in):
    at = timestamp(as_of)
    if len(recent_sets) > 500 or not 1 <= len(planned_exercises) <= 30 or len(regional_check_in) > 11:
        raise ValueError("Strength limits: 500 recent sets, 1–30 exercises, 11 regions")
    sets = [WorkSet.model_validate(row) for row in recent_sets]
    planned = [PlannedExercise.model_validate(row) for row in planned_exercises]
    check = [RegionalCheck.model_validate(row) for row in regional_check_in]
    if len({row.set_id for row in sets}) != len(sets) or len({row.region for row in check}) != len(check):
        raise ValueError("Duplicate set IDs or regional check-ins")
    for row in sets:
        if not 0 <= (at-timestamp(row.performed_at)).total_seconds()/3600 <= 24*90:
            raise ValueError("Sets must precede assessment and be within 90 days")
    work = [row for row in sets if not row.warmup]
    regional = {row.region:row for row in check}
    assessments = []
    for index, exercise in enumerate(planned):
        overlapping = [row for row in work if set(row.regions) & set(exercise.regions)]
        exact = [row for row in work if row.exercise_id == exercise.exercise_id and row.equipment == exercise.equipment]
        recent = [row for row in overlapping if (at-timestamp(row.performed_at)).total_seconds() <= 72*3600]
        prior_planned = [i+1 for i, earlier in enumerate(planned[:index])
                         if set(earlier.regions) & set(exercise.regions)]
        regional_evidence = {region:regional[region].model_dump(exclude={"region"}) if region in regional
                             else {"soreness":None, "pain":None} for region in exercise.regions}
        counts = {str(hours):sum((at-timestamp(row.performed_at)).total_seconds() <= hours*3600 for row in recent)
                  for hours in (24,48,72)}
        complete_weights = all(row.external_load_kg is not None for row in exact)
        assessments.append({"sequence":index+1, **exercise.model_dump(),
            "status":"review_reported_pain" if any(row["pain"] is True for row in regional_evidence.values())
                     else "exposure_context_only_not_recovery_clearance",
            "regional_check_in":regional_evidence,
            "overlapping_work_sets_by_lookback_hours":counts,
            "hours_since_latest_overlapping_work_set":min((at-timestamp(row.performed_at)).total_seconds()/3600
                                                          for row in overlapping) if overlapping else None,
            "recent_72h_sets_with_reported_rir":sum(row.rir is not None for row in recent),
            "recent_72h_sets_at_0_to_2_rir":sum(row.rir is not None and row.rir <= 2 for row in recent),
            "exact_exercise_equipment_history":{
                "work_sets":len(exact), "reps":sum(row.reps for row in exact),
                "external_load_volume_kg_reps":sum(row.external_load_kg*row.reps for row in exact)
                    if exact and complete_weights else None,
                "known_load_sets":sum(row.external_load_kg is not None for row in exact)},
            "earlier_planned_exercises_with_region_overlap":prior_planned,
            "mapping_provenance":"caller-confirmed exercise/equipment/region mapping; not inferred from Garmin IDs"})
    return {"analysis_version":"strength-exposure-v1", "as_of":at.isoformat(),
            "exercises":assessments, "history_work_sets":len(work),
            "excluded_warmup_sets":len(sets)-len(work),
            "limitations":["24/48/72-hour windows and 0–2 RIR grouping are descriptive choices, not recovery deadlines",
                           "Region overlap does not quantify muscle recruitment or fatigue",
                           "External-load kg-reps is descriptive; not comparable across exercises, equipment or range of motion",
                           "Bodyweight/assistance loads and unverified Garmin raw weight must remain unknown unless independently resolved",
                           "No exact repetition forecast, injury probability, tissue-recovery estimate or medical clearance",
                           "Review warmup performance, symptoms, sleep and nutrition before choosing working loads"],
            "text_is_untrusted_data":True}
