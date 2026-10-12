import base64
import pytest
from garmin_connect_mcp.writes import validate


def test_recording_above_old_tiny_limit_and_maximum():
    content=b'<gpx version="1.1">'+b' '*20000+b'</gpx>'
    params={"format":"gpx","content_base64":base64.b64encode(content).decode()}
    assert validate("upload_activity_file",params)==params
    params["content_base64"]=base64.b64encode(b'x'*(2*1024*1024+1)).decode()
    with pytest.raises(ValueError,match="2 MiB"):
        validate("upload_activity_file",params)
