import base64
from datetime import datetime, timedelta
from hashlib import sha1
import hmac
import json
import requests

GEOFOX_ENDPOINT = "https://gti.geofox.de"

def load_geofox_creds():
    with open("secrets.json") as f:
        global GEOFOX_PASS, GEOFOX_USER
        creds = json.loads(f.read())
        GEOFOX_PASS = creds["geofox_pass"]
        GEOFOX_USER = creds["geofox_user"]
        

def _get_signature(request_body: dict) -> bytes:
    """ Private function that creates the signature for geofox request. """
    key = bytes(GEOFOX_PASS, "utf-8")
    hashed = hmac.new(key, bytes(json.dumps(request_body), "utf-8"), sha1)
    signature = base64.b64encode(hashed.digest())
    return signature

def get_gti_time():
    now = datetime.now()
    
    gti_time_variable = {
        "date": now.strftime("%d.%m.%Y"),
        "time": now.strftime("%H:%M")
    }
    
    return gti_time_variable

def get_station_departures(station_name: str):
    body = {
        "version": 63,
        "station": {
            "name": station_name,
            "type": "STATION"
        },
        "time": get_gti_time(),
        "maxList": 10,
        "maxTimeOffset": 30,
        "allStationsInChangingNode": False,
        "returnFilters": False,
        "useRealtime": True,
    }
    
    headers = {
        "geofox-auth-user": GEOFOX_USER,
        "geofox-auth-signature": _get_signature(body)
    }
    
    response = requests.post(url=GEOFOX_ENDPOINT + "/gti/public/departureList", headers=headers, json=body)
    
    f_departures = []
    departures = response.json()
    
    for dep in departures.get("departures", []):
        line_name = dep["line"]["name"]
        direction = dep["line"]["direction"]
        platform  = dep.get("platform", "")
        
        time_offset = dep.get("timeOffset", 0)
        delay_seconds = dep.get("delay", 0)
        delay_minutes = int(delay_seconds / 60)
        real_minutes = time_offset + delay_minutes
        time_display = max(0, real_minutes)
        
        f_departures.append((line_name, direction, platform, time_display, delay_minutes))
    
    return f_departures