from __future__ import print_function
from datetime import datetime
from datetime import date
from PyBambooHR import PyBambooHR
from os import environ

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']
EMAIL = 'eduardo.picazo@uberall.com'

def get_environments():
    env = dict()
    env["bamboohr_subdomain"] = environ["BAMBOOHR_SUBDOMAIN"]
    env["bamboohr_api_key"] = environ["BAMBOOHR_API_KEY"]
    return env


def bamboo_hr_client(bamboohr_subdomain, bamboohr_api_key):
    return PyBambooHR.PyBambooHR(subdomain=bamboohr_subdomain, api_key=bamboohr_api_key)


def retrieve_unique_employees_id(all_employees_time_off):
    # we use sets to eliminate duplicates
    return {row['employeeId'] for row in all_employees_time_off}


def append_work_email_to_unique_employees_id(bamboo_client, unique_employees_id):
    list_of_unique_employees_id_with_work_email = list()

    for employee_id in unique_employees_id:
        employee_data = bamboo_client.get_employee(employee_id)
        work_email = employee_data['workEmail']
        unique_employees_id_with_work_email = {'employee_id': employee_id,
                                               'work_email': work_email
                                               }
        list_of_unique_employees_id_with_work_email.append(unique_employees_id_with_work_email)
    return list_of_unique_employees_id_with_work_email


def append_work_email_to_all_employees_time_off(all_employees_time_off, list_of_unique_employees_id_with_work_email):
    for employee_time_off in all_employees_time_off:
        for unique_employee_id_with_work_email in list_of_unique_employees_id_with_work_email:
            if employee_time_off['employeeId'] == unique_employee_id_with_work_email['employee_id']:
                employee_time_off["workEmail"] = unique_employee_id_with_work_email['work_email']

    return all_employees_time_off

def google_cal_auth():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def google_cal_list_events(creds):
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return

        # Prints the start and name of the next 10 events
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

    except HttpError as error:
        print('An error occurred: %s' % error)

def google_cal_insert_event(creds, name, start_date, end_date, email):
    try:
        service = build('calendar', 'v3', credentials=creds)

        event = {
            'end': {
                'date': end_date
                },
            'start': {
                'date': start_date
            },
            'summary': "OOO %s" % (name),
            'description': "%s (%s) will be OOO" % (name, email),
            'visibility': 'public'
        }
        result = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        print('Created event in gcal:', result)

    except HttpError as error:
        print('An error occurred: %s' % error)


def get_all_employees_time_off_with_work_email(email):
    env = get_environments()
    bamboohr_subdomain = env["bamboohr_subdomain"]
    bamboohr_api_key = env["bamboohr_api_key"]

    current_datetime = datetime.now()
    current_date = current_datetime.date()
    year = current_date.year
    end_of_year = date(year, 12, 31)

    bamboo_client = bamboo_hr_client(bamboohr_subdomain, bamboohr_api_key)

    all_employees_time_off = bamboo_client.get_whos_out(current_date, end_of_year)

    unique_employees_id = retrieve_unique_employees_id(all_employees_time_off)

    list_of_unique_employees_id_with_work_email = append_work_email_to_unique_employees_id(bamboo_client,
                                                                                           unique_employees_id)

    all_employees_time_off_with_work_email = append_work_email_to_all_employees_time_off(
        all_employees_time_off, list_of_unique_employees_id_with_work_email)

    # print(all_employees_time_off_with_work_email)
    filtered = filter(lambda time_off: time_off['workEmail'] == email, all_employees_time_off_with_work_email)
    return filtered

def main():
    gcal_creds = google_cal_auth()
    user_time_off = list(get_all_employees_time_off_with_work_email(EMAIL))
    print('Creating events in gcal', user_time_off)
    for time_off in user_time_off:
        google_cal_insert_event(gcal_creds, time_off['name'], time_off['start'], time_off['end'], time_off['workEmail'])


# google_cal_main()
if __name__ == '__main__':
   main()