from http import client
from django.core.management.base import BaseCommand
from datetime import timedelta, datetime
from django.utils.timezone import utc
import requests
from dotenv import load_dotenv
import os
load_dotenv()
from django.contrib.auth import get_user_model
from concurrent.futures import ThreadPoolExecutor
import time
from google.oauth2 import service_account
import googleapiclient.discovery


def get_user():
    user_object = get_user_model().objects.get(username='sseun43')
    return user_object

def get_start_times(energy_dict):
    return energy_dict['start_time']

def get_value(energy_dict):
    return energy_dict['value']

def get_mean_value(energy_data):
    return int(sum(map(get_value, energy_data)) / len(energy_data))

def get_max_value(energy_data):
    return max(map(get_value, energy_data))

def get_min_value(energy_data):
    return min(map(get_value, energy_data))

def get_first_and_third_quartile(energy_data):
    energy_data.sort(key=get_value)
    first_quartile = energy_data[int(len(energy_data) / 4)]
    third_quartile = energy_data[int(len(energy_data) * 3 / 4)]
    return (first_quartile['value'], third_quartile['value'])

def format_raw_data(raw_data):
    formatted_data = []
    list_of_start_times = list(set(map(get_start_times, raw_data)))
    for time in list_of_start_times:
        filtered_energy_data = list(filter(lambda x: x['start_time'] == time, raw_data))
        total = int(filtered_energy_data[0]['value']) + int(filtered_energy_data[1]['value'])
        formatted_data.append({'start_time': time, 'value': total, 'end_time': filtered_energy_data[0]['end_time']})
    return formatted_data

def get_url(url):
    headers = {
        'x-api-key': os.environ['X_API_KEY']
    }
    return requests.get(url, headers=headers)

def get_color(energy_value, min_data, first_quartile, mean_data, third_quartile, max_data):
    color = '1'
    if energy_value == min_data:
        color = '11'
    elif energy_value <= first_quartile and energy_value > min_data:
        color = '6'
    elif energy_value <= mean_data and energy_value > first_quartile:
        color = '5'
    elif energy_value <= third_quartile and energy_value > mean_data:
        color = '7'
    elif energy_value < max_data and energy_value > third_quartile:
        color = '9'
    elif energy_value == max_data:
        color = '10'
    return color

def get_percentage(energy_value, total_energy):
    return int(energy_value / total_energy * 100)

def get_event_text(energy_value, min_data, max_data):
    total_solar_energy = 414
    total_wind_energy = 3813
    total_green_energy = total_solar_energy + total_wind_energy
    event_text = f'{get_percentage(energy_value, total_green_energy)}% of green energy capacity'
    if energy_value == min_data:
        event_text = f'Lowest {get_percentage(energy_value, total_green_energy)}% of green energy capacity'
    elif energy_value == max_data:
        event_text = f'Highest {get_percentage(energy_value, total_green_energy)}%  of green energy production'
    return event_text


def create_event(start_time, end_time, energy_value, min_data,first_quartile, mean_data, third_quartile, max_data):

    event = {
        "summary": get_event_text(energy_value, min_data, max_data),
        "location": "Finland",
        'colorId': get_color(energy_value, min_data, first_quartile, mean_data, third_quartile, max_data),
        "start": {
            'dateTime': start_time,
            'timeZone': "UTC",
        },
        "end": {
            'dateTime': end_time,
            'timeZone': "UTC",
        },
        "transparency": "transparent",
    }
    return event

def create_events(formatted_data, min_data, first_quartile, mean_data, third_quartile, max_data):
    events = []
    for energy_data in formatted_data:
        events.append(create_event(energy_data['start_time'], energy_data['end_time'], energy_data['value'], min_data, first_quartile, mean_data, third_quartile, max_data))
    return events

# def create_google_calendar_event(events, access_token):
#     CALENDER_ID = os.environ['CALENDER_ID']
#     url = f'https://www.googleapis.com/calendar/v3/calendars/{CALENDER_ID}/events'
#     test_event = events[0]
#     headers = {
#         'Authorization': 'Bearer ' + access_token,
#         'Accept': 'application/json',
#         'Content-Type': 'application/json'
#     }

#     for event in events:
#         requests.post(url, headers=headers, json=event)
#     print("Events created")

def get_calender_service():
    service_account_info = {
        "type": "service_account",
        "project_id": os.environ['PROJECT_ID'],
        "private_key_id": os.environ['PRIVATE_KEY_ID'],
        "private_key": os.environ['PRIVATE_KEY'],
        "client_email": os.environ['CLIENT_EMAIL'],
        "client_id": os.environ['CLIENT_ID'],
        "auth_uri": os.environ['AUTH_URI'],
        "token_uri": os.environ['TOKEN_URI'],
        "auth_provider_x509_cert_url": os.environ['AUTH_PROVIDER_URL'],
        "client_x509_cert_url": os.environ['CLIENT_CERT_URL']
    }
    SCOPES = ['https://www.googleapis.com/auth/calendar.events','https://www.googleapis.com/auth/calendar.events']
    credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
    return service

    

def create_events_using_service_account(events):
    service = get_calender_service()
    CALENDER_ID = os.environ['CALENDER_ID']
    for event in events:
        service.events().insert(calendarId=CALENDER_ID, body = event).execute()





  
class Command(BaseCommand):
    help = 'Update the calendar with the current data'
  
    def handle(self, *args, **kwargs):
        """
        Update events based on the current data
        Sample api call: https://api.fingrid.fi/v1/variable/245/events/json?start_time=2022-05-12T13:06:08Z&end_time=2022-05-15T13:06:08Z

        """
        # headers = {
        #     'x-api-key': os.environ['X_API_KEY']
        # }
        # access_token = get_user().social_auth.get(provider='google-oauth2').extra_data['access_token']
        start_time = datetime.utcnow().replace(tzinfo=utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time = (datetime.utcnow().replace(tzinfo=utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        wind_variable_id = '245'
        solar_variable_id = '248'
        wind_url = f'https://api.fingrid.fi/v1/variable/{wind_variable_id}/events/json?start_time={start_time}&end_time={end_time}'
        solar_url = f'https://api.fingrid.fi/v1/variable/{solar_variable_id}/events/json?start_time={start_time}&end_time={end_time}'

        list_of_urls = [wind_url, solar_url]
        with ThreadPoolExecutor(max_workers=2) as pool:
            response_list = list(pool.map(get_url,list_of_urls))

        total_data = response_list[0].json() + response_list[1].json()
        reformed_data = format_raw_data(total_data)
        first_quartile, third_quartile = get_first_and_third_quartile(reformed_data)
        mean_data = get_mean_value(reformed_data)
        max_data = get_max_value(reformed_data)
        min_data = get_min_value(reformed_data)
        events = create_events(reformed_data, min_data, first_quartile, mean_data, third_quartile, max_data)
        # create_google_calendar_event(events, access_token)
        create_events_using_service_account(events)
        print("Events created")

        






