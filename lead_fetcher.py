import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO
from closeio_api import Client
import pycountry

api = Client(st.secrets["close_api_key"])


def check_close_if_email_exist(email):
    lead_results = api.post(
        "data/search/",
        data={
            "query": {
                "negate": False,
                "queries": [
                    {"negate": False, "object_type": "lead", "type": "object_type"},
                    {
                        "mode": "beginning_of_words",
                        "negate": False,
                        "type": "text",
                        "value": email,
                    },
                    {"negate": False, "queries": [], "type": "and"},
                ],
                "type": "and",
            },
            "results_limit": None,
            "sort": [],
        },
    )
    return len(lead_results["data"]) >= 1


class InfluencerDataFetcher:
    def __init__(self, leadtype, country_codes):
        self.leadtype = leadtype
        self.current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.country_codes = country_codes
        self.url = st.secrets["s_url"]

    def get_country_name(self, country_code):
        try:
            return pycountry.countries.get(alpha_2=country_code).name
        except AttributeError:
            return country_code

    def fetch_influencer_data(self, keyword):
        data_rows = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        followers = [6, 7] if self.leadtype == "CS" else [4, 7]
        include_socials = self.leadtype == "MSN"

        for index, country in enumerate(self.country_codes, start=1):
            country_name = self.get_country_name(country)
            status_text.text(
                f"Fetching data for keyword '{keyword}' in {country_name} ({index}/{len(self.country_codes)})"
            )
            progress_bar.progress(index / len(self.country_codes))
            request_body = {
                "0": {
                    "json": {
                        "isPremiumUser": 1,
                        "is_admin": 0,
                        "index_name": "influencer",
                        "country": [country],
                        "bio": [
                            "gmail.com",
                            "hotmail.com",
                            ".com",
                            "outlook.com",
                            keyword,
                        ],
                        "followers": followers,
                        "hashtags": [keyword],
                        # "keywords": [keyword]
                    }
                }
            }
            if include_socials:
                request_body["0"]["json"]["socials"] = ["Instagram"]

            response = requests.post(self.url, json=request_body)
            if response.status_code == 200:
                data = response.json()
                hits = data[0]["result"]["data"]["json"]["hits"]
                for hit in hits:
                    nickname = hit.get("nickname", "N/A")
                    username = hit.get("username", "N/A")
                    email = hit.get("email", "N/A")
                    instagramId = hit.get("instagram_id", "NA")
                    follower_count = (
                        int(hit.get("follower_count", 0))
                        if hit.get("follower_count")
                        else 0
                    )
                    close_email_exist = check_close_if_email_exist(email)

                    if self.leadtype == "CS":
                        if not close_email_exist and follower_count > 148000:
                            data_rows.append(
                                [
                                    nickname,
                                    f"@{username}",
                                    f"https://tiktok.com/@{username}",
                                    email,
                                    follower_count,
                                    country,
                                    "Not Imported",
                                ]
                            )
                    else:
                        if not close_email_exist:
                            data_rows.append(
                                [
                                    instagramId,
                                    f"https://www.instagram.com/{instagramId}",
                                    email,
                                    follower_count,
                                    country_name,
                                    "Not Imported",
                                ]
                            )
            else:
                print(
                    f"Failed to get data for {country_name}. Status code: {response.status_code}"
                )
        columns = (
            [
                "nickname",
                "user",
                "username",
                "email",
                "follower_count",
                "country",
                "status",
            ]
            if self.leadtype == "CS"
            else ["igid", "igurl", "email", "follower_count", "country", "status"]
        )
        df = pd.DataFrame(data_rows, columns=columns)
        return df


def login():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        st.empty()

        # Show logout button
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.success("Logged out successfully!")
            return False  # User is now logged out, return False

        st.write("You are logged in!")
        return True  # User is logged in

    else:
        title = st.empty()

        username_input = st.empty()
        password_input = st.empty()

        title.title("Login to Lead Fetcher")
        username = username_input.text_input("Username")
        password = password_input.text_input("Password", type="password")

        if st.button("Login"):
            if (
                username == st.secrets["enf_username"]
                and password == st.secrets["enf_password"]
            ):
                st.session_state.logged_in = True
                username_input.empty()  # Remove username input after successful login
                password_input.empty()  # Remove password input after successful login
                title.empty()
                return True  # Successfully logged in
            else:
                st.error("Invalid username or password.")

        return False  # User is not logged in


def main():
    if not login():
        return

    st.title("Influencer Data Fetcher")
    email_text = st.empty()
    email_data = st.text_input("Check if email exist: paste email here")

    if st.button("Check Email"):
        is_email_exist = check_close_if_email_exist(email_data)

        if is_email_exist:
            email_text.text("This email already exist in close")
        else:
            email_text.text("Email does not exist")

    use_english_speaking = st.checkbox("Use English-speaking countries only")
    is_filipino = st.checkbox("Filipino influencers only")
    keyword_input = st.text_input("Enter Keywords (comma-separated):")
    leadtype = st.selectbox("Select Lead Type:", ["CS", "MSN"])

    filipino_country_code = ["PH"]

    english_speaking_country_codes = [
        "US",
        "GB",
        "CA",
        "AU",
        "NZ",
        "IE",
        "JM",
        "TT",
        "BB",
        "BS",
        "BZ",
        "ZW",
        "GH",
        "NG",
        "PK",
        "PH",
        "KE",
        "SG",
    ]

    if is_filipino:
        country_codes = filipino_country_code
    else:
        country_codes = (
            english_speaking_country_codes
            if use_english_speaking
            else [
                "CA",
                "GB",
                "AU",
                "KW",
                "AT",
                "YT",
                "TN",
                "JP",
                "GY",
                "SH",
                "MF",
                "GT",
                "VE",
                "TF",
                "CV",
                "AZ",
                "GG",
                "KE",
                "SS",
                "MM",
                "LI",
                "MQ",
                "CR",
                "PS",
                "ES",
                "GW",
                "AX",
                "SL",
                "PH",
                "TG",
                "RU",
                "HT",
                "KR",
                "WS",
                "AW",
                "AF",
                "BV",
                "BS",
                "GE",
                "KY",
                "MK",
                "SY",
                "HK",
                "CL",
                "ZW",
                "BQ",
                "NL",
                "GQ",
                "SZ",
                "OM",
                "HM",
                "RO",
                "ZA",
                "MZ",
                "TT",
                "BH",
                "CG",
                "LB",
                "RE",
                "EE",
                "BD",
                "ET",
                "PE",
                "GS",
                "EC",
                "VA",
                "MU",
                "AS",
                "PM",
                "CU",
                "IO",
                "VN",
                "BJ",
                "GR",
                "GD",
                "BZ",
                "CN",
                "ME",
                "TH",
                "GU",
                "KM",
                "LA",
                "ML",
                "DE",
                "SR",
                "GM",
                "MV",
                "TO",
                "AG",
                "GN",
                "CW",
                "PA",
                "PG",
                "NC",
                "HR",
                "PW",
                "VI",
                "KH",
                "PR",
                "PF",
                "NI",
                "CO",
                "MR",
                "BW",
                "FJ",
                "LV",
                "SJ",
                "BM",
                "UG",
                "BA",
                "GA",
                "TD",
                "CC",
                "KZ",
                "PN",
                "GP",
                "SD",
                "DM",
                "QA",
                "BB",
                "TR",
                "DK",
                "MH",
                "YE",
                "AQ",
                "ST",
                "TM",
                "KP",
                "PT",
                "ER",
                "GI",
                "MN",
                "XK",
                "AI",
                "MW",
                "TV",
                "MD",
                "BN",
                "UM",
                "FI",
                "GH",
                "DO",
                "MP",
                "CZ",
                "MA",
                "HN",
                "IL",
                "MG",
                "LU",
                "AM",
                "TC",
                "FK",
                "AO",
                "CY",
                "ID",
                "UZ",
                "BI",
                "AL",
                "BL",
                "BO",
                "KG",
                "AE",
                "PY",
                "TZ",
                "AR",
                "PK",
                "NP",
                "NZ",
                "CH",
                "NF",
                "SE",
                "LC",
                "UY",
                "MX",
                "SO",
                "MS",
                "NO",
                "SC",
                "NR",
                "BT",
                "RW",
                "HU",
                "SI",
                "SX",
                "IN",
                "GF",
                "IT",
                "SG",
                "IE",
                "AD",
                "IS",
                "FM",
                "FO",
                "KN",
                "NE",
                "FR",
                "DJ",
                "LR",
                "TW",
                "JO",
                "GL",
                "LY",
                "KI",
                "CK",
                "LS",
                "MC",
                "MY",
                "WF",
                "SA",
                "BG",
                "BF",
                "BR",
                "LT",
                "JE",
                "DZ",
                "SB",
                "LK",
                "SM",
                "NG",
                "SK",
                "CM",
                "NA",
                "EG",
                "VC",
                "BY",
                "UA",
                "CX",
                "NU",
                "JM",
                "ZM",
                "SN",
                "BE",
                "CF",
                "IR",
                "IQ",
                "TL",
                "IM",
                "MO",
                "SV",
                "MT",
                "PL",
                "RS",
                "CI",
                "EH",
                "CD",
                "TJ",
                "VU",
                "TK",
                "VG",
            ]  # Add all countries as needed
        )

    if st.button("Fetch Data"):
        fetcher = InfluencerDataFetcher(leadtype, country_codes)
        keywords = [kw.strip() for kw in keyword_input.split(",") if kw.strip()]
        tabs = st.tabs(keywords)

        for tab, keyword in zip(tabs, keywords):
            with tab:
                st.header(f"Results for '{keyword}'")
                data = fetcher.fetch_influencer_data(keyword)
                st.dataframe(data)


if __name__ == "__main__":
    main()
