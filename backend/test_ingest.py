import requests
import pytest

def test_upload():
    url = "http://127.0.0.1:8000/api/v1/ingest"
    session_id = "1788cba5-7916-484b-a34b-5839aaef65f7"
    
    # Create dummy file matching finance domain
    file_bytes = b"Date,Description,Amount\n2024-01-01,Coffee,5.00"
    
    files = {"file": ("test.csv", file_bytes, "text/csv")}
    data = {"domain": "finance", "session_id": session_id}
    
    try:
        resp = requests.post(url, files=files, data=data, timeout=10)
    except requests.exceptions.RequestException:
        pytest.skip("Local backend server is not running for integration ingest test")
    print("STATUS:", resp.status_code)
    print("RESPONSE:", resp.text)

if __name__ == "__main__":
    test_upload()
