from closeio_api import Client
from datetime import datetime, timedelta
import streamlit as st
import pytz

api = Client(st.secrets["close_api_key"])


def get_latest_email(lead_id):
    response = api.get(
        "activity/email/",
        params={
            "lead_id": lead_id,
            "sort": "-date_created",
            "limit": 1,  # Get the most recent email only
        },
    )
    if response["data"]:
        latest_email = response["data"][0]
        utc_dt = datetime.fromisoformat(latest_email.get("date_created"))
        sg_ph_tz = pytz.timezone("Asia/Singapore")
        sg_ph_time = utc_dt.astimezone(sg_ph_tz)
        formatted_date = sg_ph_time.strftime("%Y-%m-%d")
        return formatted_date
    
    return None

def get_close_data(email, days_back=None):
    query = {
        "negate": False,
        "queries": [
            {"negate": False, "object_type": "lead", "type": "object_type"},
            {
                "mode": "beginning_of_words",
                "negate": False,
                "type": "text",
                "value": email,
            },
        ],
        "type": "and",
    }

    if days_back is not None:
        query["queries"].append(
            {
                "negate": False,
                "queries": [
                    {
                        "negate": False,
                        "related_object_type": "activity.email",
                        "related_query": {
                            "negate": False,
                            "queries": [
                                {
                                    "condition": {
                                        "type": "term",
                                        "values": ["outgoing"],
                                    },
                                    "field": {
                                        "field_name": "direction",
                                        "object_type": "activity.email",
                                        "type": "regular_field",
                                    },
                                    "negate": False,
                                    "type": "field_condition",
                                },
                                {
                                    "condition": {
                                        "before": {"type": "now"},
                                        "on_or_after": {
                                            "direction": "past",
                                            "moment": {"type": "now"},
                                            "offset": {
                                                "days": days_back,
                                                "hours": 0,
                                                "minutes": 0,
                                                "months": 0,
                                                "seconds": 0,
                                                "weeks": 0,
                                                "years": 0,
                                            },
                                            "type": "offset",
                                            "which_day_end": "start",
                                        },
                                        "type": "moment_range",
                                    },
                                    "field": {
                                        "field_name": "date",
                                        "object_type": "activity.email",
                                        "type": "regular_field",
                                    },
                                    "negate": False,
                                    "type": "field_condition",
                                },
                            ],
                            "type": "and",
                        },
                        "this_object_type": "lead",
                        "type": "has_related",
                    }
                ],
                "type": "and",
            }
        )

    lead_results = api.post(
        "data/search/",
        data={
            "limit": None,
            "query": query,
            "results_limit": None,
            "sort": [
                {
                    "direction": "asc",
                    "field": {
                        "field_name": "num_emails",
                        "object_type": "lead",
                        "type": "regular_field",
                    },
                }
            ],
        },
    )

    if len(lead_results["data"]) == 0:
        return None
    
    else:
        lead_id = lead_results["data"][0]["id"]
        if days_back is not None:
            date_last_email = get_latest_email(lead_id)
            if date_last_email:
                return f"Contacted Date: {date_last_email}"
            else:
                return f"{email} Contacted but older than {days_back} days"
        else:
            return f"{email} Contacted but no specific days_back check applied"
