import logging
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import json
import os
from models.apollo import ApolloLead

logger = logging.getLogger("EnrichmentService")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "location_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

_geocoder = Nominatim(user_agent="lead_gen_app_123")
_tf = TimezoneFinder()
_location_cache = load_cache()

def enrich_lead_location_and_tz(lead: ApolloLead) -> ApolloLead:
    """
    Enriches a lead with detailed location, timezone, and business hours.
    Prioritizes structured location data, falls back to geopy.
    """
    if not lead.location:
        return lead
        
    lead.apollo_location = lead.location
    loc_key = lead.location.lower().strip()
    
    if loc_key in _location_cache:
        cached = _location_cache[loc_key]
        if cached.get("timezone"):  # Only use cache if a valid timezone was found previously
            lead.city = cached.get("city") or lead.city
            lead.state = cached.get("state") or lead.state
            lead.country = cached.get("country") or lead.country
            lead.timezone = lead.timezone or cached.get("timezone")
            lead.utc_offset = lead.utc_offset or cached.get("utc_offset")
            return lead
            
    # Priority 1: Existing timezone from Apify/Database (already on lead)
    if lead.timezone and lead.timezone != "UTC":
        # We have a valid timezone, skip geocoding for timezone, just cache it
        _location_cache[loc_key] = {
            "city": lead.city,
            "state": lead.state,
            "country": lead.country,
            "timezone": lead.timezone,
            "utc_offset": lead.utc_offset
        }
        save_cache(_location_cache)
        return lead

    try:
        query_parts = []
        if lead.city: query_parts.append(lead.city)
        if lead.state: query_parts.append(lead.state)
        if lead.country: query_parts.append(lead.country)
        elif lead.location: query_parts.append(lead.location)
        
        query_str = ", ".join(query_parts) if query_parts else lead.location
        logger.info(f"Geocoding with query: {query_str}")
        
        location = _geocoder.geocode(query_str, exactly_one=True, addressdetails=True)
        if location:
            addr = location.raw.get('address', {})
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county')
            state = addr.get('state')
            country = addr.get('country')
            
            lat, lng = location.latitude, location.longitude
            tz_name = _tf.timezone_at(lng=lng, lat=lat)
            
            # Fallback to country_timezones if TimezoneFinder fails
            if not tz_name and addr.get('country_code'):
                import pytz
                cc = addr.get('country_code').upper()
                if cc in pytz.country_timezones:
                    tz_list = pytz.country_timezones[cc]
                    if tz_list:
                        tz_name = tz_list[0]
            
            utc_offset_str = None
            if tz_name:
                import pytz
                from datetime import datetime
                tz = pytz.timezone(tz_name)
                # Ensure we use a naive datetime to get the correct UTC offset for the timezone currently
                offset = tz.utcoffset(datetime.utcnow())
                hours = int(offset.total_seconds() // 3600)
                minutes = int((abs(offset.total_seconds()) % 3600) // 60)
                sign = "+" if hours >= 0 else "-"
                utc_offset_str = f"UTC{sign}{abs(hours):02d}:{minutes:02d}"
                
            lead.city = city
            lead.state = state
            lead.country = country
            lead.timezone = tz_name or "UTC"
            lead.utc_offset = utc_offset_str or "UTC+00:00"
            
            _location_cache[loc_key] = {
                "city": city,
                "state": state,
                "country": country,
                "timezone": lead.timezone,
                "utc_offset": lead.utc_offset
            }
            save_cache(_location_cache)
        else:
            fallback_tz = None
            country_name_lower = (lead.country or lead.location or "").lower().strip()
            if country_name_lower:
                import pytz
                for code, name in pytz.country_names.items():
                    if name.lower() == country_name_lower:
                        tz_list = pytz.country_timezones.get(code)
                        if tz_list:
                            fallback_tz = tz_list[0]
                        break
                        
            lead.timezone = fallback_tz or "UTC"
            lead.utc_offset = "UTC+00:00" # We could calculate offset for fallback_tz if needed, but this is a deep fallback
            if fallback_tz:
                import pytz
                from datetime import datetime
                tz = pytz.timezone(fallback_tz)
                offset = tz.utcoffset(datetime.utcnow())
                hours = int(offset.total_seconds() // 3600)
                minutes = int((abs(offset.total_seconds()) % 3600) // 60)
                sign = "+" if hours >= 0 else "-"
                lead.utc_offset = f"UTC{sign}{abs(hours):02d}:{minutes:02d}"

            _location_cache[loc_key] = {
                "city": lead.city,
                "state": lead.state,
                "country": lead.country,
                "timezone": lead.timezone,
                "utc_offset": lead.utc_offset
            }
            save_cache(_location_cache)
    except Exception as e:
        logger.error(f"Error geocoding location '{lead.location}': {e}")
        # Cache the fallback to prevent infinite retries on network errors
        fallback_tz = None
        country_name_lower = (lead.country or lead.location or "").lower().strip()
        if country_name_lower:
            import pytz
            for code, name in pytz.country_names.items():
                if name.lower() == country_name_lower:
                    tz_list = pytz.country_timezones.get(code)
                    if tz_list:
                        fallback_tz = tz_list[0]
                    break
                    
        lead.timezone = fallback_tz or "UTC"
        lead.utc_offset = "UTC+00:00"
        if fallback_tz:
            import pytz
            from datetime import datetime
            tz = pytz.timezone(fallback_tz)
            offset = tz.utcoffset(datetime.utcnow())
            hours = int(offset.total_seconds() // 3600)
            minutes = int((abs(offset.total_seconds()) % 3600) // 60)
            sign = "+" if hours >= 0 else "-"
            lead.utc_offset = f"UTC{sign}{abs(hours):02d}:{minutes:02d}"

        _location_cache[loc_key] = {
            "city": lead.city,
            "state": lead.state,
            "country": lead.country,
            "timezone": lead.timezone,
            "utc_offset": lead.utc_offset
        }
        save_cache(_location_cache)

    return lead
