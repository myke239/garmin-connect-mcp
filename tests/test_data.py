import pytest

from garmin_connect_mcp.data import activity, validate_id, validate_range
from garmin_connect_mcp.service import GarminService


def test_units_missing_metrics_and_location_exclusion():
    result = activity({"activityId": 1, "distance": 5000, "duration": 1200,
                       "averageSpeed": 4, "startLatitude": 40, "startLongitude": -120})
    assert result["distance_m"] == 5000
    assert result["average_pace_s_km"] == 250
    assert result["average_heart_rate_bpm"] is None
    assert "Latitude" not in str(result) and "Longitude" not in str(result)


@pytest.mark.parametrize("value", ["0", "../1", "-1", "١", "1/2", "9"*21])
def test_reject_bad_id(value):
    with pytest.raises(ValueError):
        validate_id(value)


@pytest.mark.parametrize("start,end", [("2026-01-01", "2026-05-01"), ("2026-02-30", "2026-03-01"), ("2026-02-02", "2026-02-01")])
def test_reject_bad_dates(start, end):
    with pytest.raises(ValueError):
        validate_range(start, end)


def test_pagination_and_no_credentials_needed():
    class FakeService(GarminService):
        def call(self, method, *args, **kwargs):
            assert method == "connectapi"
            assert kwargs["params"]["limit"] == 3
            return [{"activityId": i} for i in [3,2,1]]
    page = FakeService().list_activities("2026-10-01", "2026-10-11", limit=2)
    assert [row["activity_id"] for row in page["activities"]] == ["3", "2"]
    assert page["next_cursor"] == 2


def test_strength_filter_uses_parent_and_subtype():
    class FakeService(GarminService):
        def call(self, method, *args, **kwargs):
            assert kwargs["params"]["activityType"] == "fitness_equipment"
            assert kwargs["params"]["activitySubType"] == "strength_training"
            return []
    assert not FakeService().list_activities("2026-10-01", "2026-10-11", "strength_training")["activities"]
