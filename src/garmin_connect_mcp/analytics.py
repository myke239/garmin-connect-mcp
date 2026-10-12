"""Bounded, time-aware analytics; missing samples never become zero."""
from .data import number

CHANNELS = {'heart_rate': ('directHeartRate', 'heart_rate_bpm'),
    'power': ('directPower', 'power_w'), 'cadence': ('directCadence', 'cadence_raw'),
    'speed': ('directSpeed', 'speed_m_s'), 'elevation': ('directElevation', 'elevation_m')}


def samples(raw, metric, maximum):
    if metric not in CHANNELS or isinstance(maximum, bool) or not 1 <= maximum <= 1000:
        raise ValueError('Choose heart_rate/power/cadence/speed/elevation; 1–1000 points')
    descriptors = {d.get('key'): d for d in (raw.get('metricDescriptors') or []) if isinstance(d, dict)}
    channel, field = CHANNELS[metric]
    if metric=='cadence' and 'directDoubleCadence' in descriptors:channel='directDoubleCadence'
    if channel not in descriptors:
        return {'available': False, 'samples': [], 'metric': metric}
    def read(values, key):
        index = descriptors.get(key, {}).get('metricsIndex')
        return number(values[index]) if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(values) else None
    source = raw.get('activityDetailMetrics') or []
    if not isinstance(source, list):
        raise ValueError('Unsupported sample response')
    rows = [{'timestamp_unix_ms': read(row.get('metrics') or [], 'directTimestamp'),
             field: read(row.get('metrics') or [], channel)} for row in source[:10000] if isinstance(row, dict)]
    count = len(rows)
    if count > maximum:
        rows = [rows[round(i*(count-1)/(maximum-1))] for i in range(maximum)] if maximum > 1 else rows[:1]
    return {'available': any(row[field] is not None for row in rows), 'metric': metric,
        'samples': rows, 'returned_points': len(rows), 'source_points': count,
        'truncated': len(source) > 10000, 'downsampled': len(rows) < count, 'server_may_downsample': True, 'source_unit': descriptors[channel].get('unit'),
        'unit_factor_applied': False, 'unit_note': 'Descriptor factors are Garmin display metadata; cadence unit follows source descriptor, not assumed rpm.'}


def analyse(rows):
    """Power best efforts require contiguous, approximately one-second samples."""
    stamps = [number(row.get('timestamp_s')) for row in rows]
    regular = len(rows) >= 2 and all(a is not None and b is not None and .95 <= b-a <= 1.05 for a,b in zip(stamps, stamps[1:]))
    powers = [number(row.get('power_w')) for row in rows]
    curve = []
    for duration in (5, 30, 60, 300, 1200):
        best = None
        if regular and len(rows) >= duration:
            total, missing = 0., 0
            for i, value in enumerate(powers):
                total += value if value is not None and value >= 0 else 0
                missing += int(value is None or value < 0)
                if i >= duration:
                    old = powers[i-duration]
                    total -= old if old is not None and old >= 0 else 0
                    missing -= int(old is None or old < 0)
                if i+1 >= duration and missing == 0:
                    best = max(best or 0, total/duration)
        curve.append({'duration_s': duration, 'best_average_power_w': best})
    pairs = []
    for row in rows:
        hr, speed = number(row.get('heart_rate_bpm')), number(row.get('speed_m_s'))
        if hr is not None and speed is not None and hr > 0 and speed > 0:
            pairs.append((hr,speed))
    drift = None
    # Require near-continuous timestamps and substantial paired coverage. This is
    # an observational whole-session estimate, not a diagnostic or steady-state claim.
    if regular and len(rows) >= 600 and len(pairs) == len(rows):
        mid = len(rows)//2
        first = sum(h for h,s in pairs[:mid])/sum(s for h,s in pairs[:mid])
        second = sum(h for h,s in pairs[mid:])/sum(s for h,s in pairs[mid:])
        drift = 100*(second/first-1)
    return {'samples': len(rows), 'one_second_contiguous': regular,
        'power_curve': curve, 'heart_rate_speed_drift_percent': drift,
        'paired_hr_speed_points': len(pairs),
        'method': 'Equal-time halves of HR/speed ratio; stops/gaps/missing pairs prevent drift. Power windows use full contiguous 1 Hz samples, including measured zero watts. No physiological diagnosis.'}
