from garmin_connect_mcp.data import heart_rate_samples, splits, strength_sets
from garmin_connect_mcp.service import GarminService


def test_samples_resolve_indices_and_bound_results():
    raw = {"metricDescriptors": [{"key":"directHeartRate", "metricsIndex":1},
                                  {"key":"directTimestamp", "metricsIndex":0},
                                  {"key":"directLatitude", "metricsIndex":2}],
           "activityDetailMetrics": [{"metrics":[1000+i, 120+i, 40]} for i in range(10)]}
    result = heart_rate_samples(raw, 3)
    assert len(result["samples"]) == 3
    assert result["samples"][-1] == {"timestamp_unix_ms":1009, "heart_rate_bpm":129}
    assert result["downsampled"]


def test_missing_channels_are_unavailable():
    assert heart_rate_samples({}, 5)["available"] is False
    assert strength_sets({})["available"] is False
    assert splits({})["available"] is False


def test_splits_omit_locations():
    result = splits({"activityId":1,"lapDTOs":[{"lapIndex":1,"distance":1000,"startLatitude":40}]})
    assert result["splits"][0]["distance_m"] == 1000
    assert "Latitude" not in str(result)


def test_summary_missing_metrics_and_partial_coverage():
    class Fake(GarminService):
        def list_activities(self, *args, **kwargs):
            cursor = kwargs["cursor"]
            return {"activities":[{"activity_id":str(cursor), "distance_m":None,
                                    "duration_s":10, "activity_type":"running"}],
                    "next_cursor":cursor+50}
    result = Fake().get_training_summary("2026-10-01","2026-10-11")
    assert not result["coverage_complete"]
    assert result["duration_s"]["value"] == 100
    assert result["distance_m"]["value"] is None
    assert result["distance_m"]["activities_missing_metric"] == 10
