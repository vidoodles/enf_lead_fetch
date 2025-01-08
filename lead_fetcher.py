import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO
from closeio_api import Client
import pycountry
import re
from googleapiclient.discovery import build

api = Client(st.secrets["close_api_key"])
yt_api_key = st.secrets["youtube_api_key"]
youtube = build('youtube', 'v3', developerKey=yt_api_key)


# Functions from your script
def search_videos(query, max_results=1000):
    videos = []
    next_page_token = None

    while len(videos) < max_results:
        request = youtube.search().list(
            q=query,
            part='snippet',
            type='channel',
            maxResults=min(max_results - len(videos), 50),
            pageToken=next_page_token
        )
        response = request.execute()
        videos.extend(response['items'])
        next_page_token = response.get('nextPageToken')

        if not next_page_token:
            break

    return videos

def get_video_details(video_id):
    request = youtube.videos().list(
        part='snippet,statistics',
        id=video_id
    )
    response = request.execute()
    return response['items'][0]

def get_channel_details(channel_id):
    request = youtube.channels().list(
        part='snippet,statistics,contentDetails',
        id=channel_id
    )
    response = request.execute()
    return response['items'][0]


def extract_emails(description):
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    return email_pattern.findall(description)

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
    def __init__(self, leadtype, country_codes, follower_range):
        self.leadtype = leadtype
        self.current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.country_codes = country_codes
        self.url = st.secrets["s_url"]
        self.follower_range = follower_range

    def get_country_name(self, country_code):
        try:
            return pycountry.countries.get(alpha_2=country_code).name
        except AttributeError:
            return country_code

    def fetch_influencer_data(self, keyword, hashtag, bio, platforms):
        data_rows = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        followers = self.follower_range
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
                        "bio": ["gmail.com", "hotmail.com", ".com", "outlook.com"],
                        "followers": followers,
                    }
                }
            }
            if platforms:
                request_body["0"]["json"]["socials"] = platforms
            if hashtag:
                request_body["0"]["json"]["hashtags"] = [hashtag]
            if keyword:
                request_body["0"]["json"]["keywords"] = [keyword]
            if bio:
                request_body["0"]["json"]["bio"].append(bio)

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
                    youtube_channel_id = hit.get("youtube_channel_id", "NA")
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
                                    f"https://www.youtube.com/channel/{youtube_channel_id}"
                                ]
                            )
                    else:
                        if not close_email_exist:
                            data_rows.append(
                                [
                                    nickname,
                                    f"https://www.instagram.com/{instagramId}",
                                    email,
                                    f"https://tiktok.com/@{username}",
                                    follower_count,
                                    country_name,
                                    "Not Imported",
                                    f"https://www.youtube.com/channel/{youtube_channel_id}"
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
                "youtube"
            ]
            if self.leadtype == "CS"
            else [
                "nickname",
                "igurl",
                "email",
                "tiktokurl",
                "follower_count",
                "country",
                "status",
                "youtube"
            ]
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
    st.sidebar.title("Navigation")
    options = ["Tiktok and Instagram Scraper", "Youtube Scraper", "Close Email Checker"]
    selected_option = st.sidebar.radio("Select an Option", options)
    if selected_option == "Tiktok and Instagram Scraper":
        st.title("Influencer Data Fetcher")
        st.text("Use the slider to select the follower count:")
        left_value, right_value = st.slider(
            "Follower Count", min_value=1, max_value=9, value=(1, 9)
        )

        labels = [
            "250",
            "500",
            "1K",
            "10k",
            "50k",
            "100k",
            "500k",
            "1M",
            "Infinite",
        ]

        follower_range = []

        st.write(
            f"You Selected: Above {labels[left_value - 1]} to {labels[right_value - 1]} Followers"
        )
        all_countries = [
            "US",
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
            "PH",
            "KE",
            "SG",
            "PL",
            "MX",
            "NL",
            "CH",
            "FR",
            "SL",
            
        ]
        follower_range.append(left_value)
        follower_range.append(right_value)

        leadtype = st.selectbox("Select Lead Type:", ["CS", "MSN"])
        st.divider()
        st.text(
            "Country Selection: Use either english speaking countries, PH, or Select multiple from the dropdown below. I Suggest using the English speaking countries if you selected MSN above"
        )
        use_english_speaking = st.checkbox("Use English-speaking countries only")
        is_filipino = st.checkbox(
            "Filipino influencers only", disabled=use_english_speaking
        )
        is_disabled = use_english_speaking or is_filipino
        st.text("Or Select from here")
        selected_options = st.multiselect(
            "Select multiple Country by Country Code",
            all_countries,
            disabled=is_disabled,
        )
        st.divider()
        st.text("Social Platforms to check if the influencer has Youtube, or Instagram, ")
        social_platforms = st.multiselect(
            "Select if influencer has",
            ["Instagram", "Youtube"]
        )
        st.divider()
        st.text(
            "For Advanced Search: use the inputs to filter leads by Bio, Hashtag used, and Caption keywords i suggest using 1 input at a time"
        )
        keyword_input = st.text_input("Caption Keywords: (Optional)")
        bio_keywords = st.text_input("Bio Keywords:  (Optional)")
        hashtag_keywords = st.text_input("Hashtag Keywords:  (Optional)")

        filipino_country_code = ["PH"]

        if is_filipino:
            country_codes = filipino_country_code
        elif use_english_speaking:
            country_codes = (
                english_speaking_country_codes
                if use_english_speaking
                else all_countries
            )
        elif selected_options:
            country_codes = selected_options

        else:
            country_codes = all_countries

        if st.button("Fetch Data"):
            fetcher = InfluencerDataFetcher(leadtype, country_codes, follower_range)
            keywords = keyword_input
            active_keywords = [
                keyword
                for keyword in [keywords, bio_keywords, hashtag_keywords]
                if keyword
            ]

            header_text = f"Results for {', '.join(active_keywords) if active_keywords else 'no keywords'}"

            st.header(header_text)
            data = fetcher.fetch_influencer_data(
                keywords, bio_keywords, hashtag_keywords, social_platforms
            )
            st.dataframe(data)
    elif selected_option == 'Close Email Checker':
        email_text = st.empty()
        email_data = st.text_input("Check if email exist: paste email here")

        if st.button("Check Email"):
            is_email_exist = check_close_if_email_exist(email_data)

            if is_email_exist:
                email_text.text("This email already exist in close")
            else:
                email_text.text("Email does not exist")
    else:

        # Streamlit App
        st.title("YouTube Video & Channel Data Extractor")

        # User Input
        search_query = st.text_input("Search Videos use hashtag / username / or keywords")
        col1, col2 = st.columns([1, 1])  # Equal width columns
        with col1:
            from_value = st.number_input("Subscriber Count From", min_value=0, max_value=9999999999, value=0, step=1)

        with col2:
            to_value = st.number_input("Subscriber Count To", min_value=0, max_value=9999999999, value=10, step=1)

        max_results = st.number_input("Max Results", min_value=1, max_value=9999999999, value=50, disabled=True)


        if st.button("Fetch Data"):
            added_channel_ids = set()
            if search_query:
                try:
                    st.info("Fetching videos... This may take some time.")
                    channels = search_videos(search_query, max_results)

                    # Store data in a DataFrame
                    data = []
                    for channel in channels:
                        channel_id = channel['snippet']['channelId']
                        if channel_id not in added_channel_ids:
                            channel_details = get_channel_details(channel_id)
                            channel_url = f"https://www.youtube.com/channel/{channel_id}"
                            emails = extract_emails(channel_details['snippet'].get('description', ''))
                            subscribers = channel_details['statistics'].get('subscriberCount', 'N/A'),


                            if from_value <= int(subscribers[0]) <= to_value:
                                data.append({
                                    'Thumbnail': channel['snippet']['thumbnails']['default']['url'],
                                    'Channel Name': channel_details['snippet']['title'],
                                    'Subscribers': channel_details['statistics'].get('subscriberCount', 'N/A'),
                                    'Channel URL': channel_url,
                                    'Country': channel_details['snippet'].get('country', 'N/A'),
                                    'Emails': ', '.join(emails) if emails else 'N/A',
                                })

                                added_channel_ids.add(channel_id)

                    if data:
                        df = pd.DataFrame(data)
                        st.write("### Extracted Data Table")

                        st.data_editor(
                            df,
                            column_config={
                                "Thumbnail": st.column_config.ImageColumn(
                                    "User Image", help="Streamlit app preview screenshots"
                                ),
                                "Channel Name": st.column_config.TextColumn(
                                    "Channel Name", help="Channel Name"
                                ),
                                "Subscribers": st.column_config.TextColumn(
                                    "Subscribers", help="Number of Subscribers"
                                ),
                                "Channel URL": st.column_config.TextColumn(
                                    "Channel URL", help="User URL"
                                ),
                                "Country": st.column_config.TextColumn(
                                    "Channel URL", help="User URL"
                                ),
                                "Emails": st.column_config.TextColumn(
                                    "Emails", help="User URL"
                                )
                            },
                            hide_index=True,
                        )

                    else:
                        st.warning("No videos met the criteria (e.g., view count below 50,000).")

                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please enter a search query.")
        else:
            st.write("Enter a search term and click 'Fetch Data' to proceed.")


footer = """<style>
a:link , a:visited{
color: blue;
background-color: transparent;
text-decoration: underline;
}

a:hover,  a:active {
color: red;
background-color: transparent;
text-decoration: underline;
}

.footer {
position: fixed;
left: 0;
bottom: 0;
width: 100%;
background-color: white;
color: black;
text-align: center;
}
</style>
<div class="footer">
<p>Disclaimer: This tool is under development and is continuously improving thru collaborations and suggestions feel free to give feedbacks thanks - Harold</p>
</div>
"""

st.markdown(footer, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
