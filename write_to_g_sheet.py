#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Program: Write to G Sheet
Programmer: Michael Fryar, Research Fellow, EPoD
Date created: January 5, 2017

Purpose: Establish SSH tunnel to edX Analytics API, download learner
data, and write data to Google Sheets via Sheets API.
"""

# Standard library imports
import csv         # For reading data in comma separated value format
import os          # For manipulating paths and changing directory
import subprocess  # For spawning ssh tunnel
import time        # For calculating run time

# Third-party imports
import httplib2                  # "A comprehensive HTTP client library"
import requests                  # "HTTP for Humans"
from apiclient import discovery  # For acessing Google Sheets API
# To install apiclient: 'pip install --upgrade google-api-python-client'

# User-written imports
from get_credentials import get_credentials
# For getting OAuth2 credentials to interact with Google Sheets API

# Start timer
start_time = time.time()


def ssh():
    """SSH tunnel to EPoDX API"""
    # Change to directory containing configuration files.
    home_dir = os.path.expanduser('~')
    epodx_dir = os.path.join(home_dir, 'Documents/epodx')
    os.chdir(epodx_dir)

    # Establish SHH tunnel in background that auto-closes.
    # -f "fork into background"
    # -F "use configuration file"
    # -o ExistOnForwardFailure=yes "wait until connection and port
    #     forwardings are set up before placing in background"
    # sleep 10 "give Python script 10 seconds to start using tunnel and
    #     close tunnel after python script stops using it"
    # Ref 1: https://www.g-loaded.eu/2006/11/24/auto-closing-ssh-tunnels/
    # Ref 2: https://gist.github.com/scy/6781836

    config = "-F ./ssh-config epodx-analytics-api"
    option = "-o ExitOnForwardFailure=yes"
    ssh = "ssh -f {} {} sleep 10".format(config, option)
    subprocess.run(ssh, shell=True)


# Read secret token needed to connect to API from untracked file.
with open("hks_secret_token.txt", "r") as myfile:
    hks_secret_token = myfile.read().replace('\n', '')


def write_to_g_sheet(course, sheet, selection='both'):
    """Downloads learner data from EPoDx and writes to Google Sheets.

    edX stores identifiable information about learners separately from
    problem response data, which is identifiable by user_id only.  This
    function downloads learner data and problem response data via the
    edX Analytics API and then writes this data to a Google Sheet via
    the Sheets API.

    Args:
        course (str): Three letter course code. Known values are:
            AGG - Aggregating Evidence
            COM - Commissioning Evidence
            CBA - Cost-Benefit Analysis
            DES - Descriptive Evidence
            IMP - Impact Evaluations
            SYS - Systematic Approaches to Policy Decisions

        sheet (str): Alphanumeric abbreviation for dashboard.  When we
        have multiple cohorts completing the same unit simultaneously,
        we need multiple dashboards for each unit.  Known values are:
            AGG - Aggregating Evidence
            COM - Commissioning Evidence
            CBA - Cost-Benefit Analysis
            DES1 - Descriptive Evidence 1
            DES2 - Descriptive Evidence 2
            IMP1 - Impact Evaluations 1
            IMP2 - Impact Evaluations 2
            SYS - Systematic Approaches to Policy Decisions

        selection (str): Specifies whether to download and write only learner
        profiles, only problem responses or both. Known values are:
            both - Download and write both learner profiles & problem responses
            problems - Only download problem responses
            profiles - Only download learner profiles
    """
    course_id = "course-v1:epodx+BCURE-{}+2016_v1".format(course)
    if sheet == "AGG":
        spreadsheetId = "1uMAyKZYtoVLzqpknBxOGbkLjR7-AMqlEEowdFqSc3pw"
    elif sheet == "COM":
        spreadsheetId = "1z6xR_xspemndfyQ_hOoYKwBZAjEEA2nqItG__plOgmU"
    elif sheet == "CBA":
        spreadsheetId = "1-b-1r5CJIWEmGZ0R_vOVJLnmAvCntL88HXPle4XaiJ0"
    elif sheet == "DES1":
        spreadsheetId = "1Yh3MQVz8AddovX1hKYNTwQ23C7OnDmJ9v0T39-lUvPU"
    elif sheet == "DES2":
        spreadsheetId = "1tOJoX60NT4Zfmne8SkWuOND2-xIYMujf-0500kRxfog"
    elif sheet == "IMP1":
        spreadsheetId = "1HUDWhXwr4Ekcs4lsqyGE6qoT4OsPaigH42zbsiY39NE"
    elif sheet == "IMP2":
        spreadsheetId = "1HdbFZG9eunByuWE4KNkx9hmJ9HvxQitv7MuivZi8ouo"
    elif sheet == "SYS":
        spreadsheetId = "1h_RW5_-BduGg9__3wO9HZj7A0ch0DAqY5IQrZlI9Ow4"
    else:
        raise NameError("Sheet abbreviation not recognized.")

    if selection == "both":
        print(
            "Downloading and writing learner profiles and problem responses."
        )

    if selection in ("both", "profiles"):
        # Define parameters for extracting learner profile data.
        learner_profile_report_url = "http://localhost:18100/api/v0/learners/"
        headers = {
            "Authorization": "Token {}".format(hks_secret_token),
            "Accept": "text/csv",
        }
        # The list of fields you've requested.
        # Leave this parameter off to see the full list of fields.
        fields = ','.join(["user_id", "username", "name", "email", "language",
                           "location", "year_of_birth", "gender",
                           "level_of_education", "mailing_address", "goals",
                           "enrollment_mode", "segments", "cohort", "city",
                           "country", "enrollment_date", "last_updated"])
        params = {
            "course_id": course_id,
            "fields": fields,
        }
        # Download learner data.
        with requests.Session() as s:
            download = s.get(
                learner_profile_report_url, headers=headers, params=params)
        # Decode learner data.
        decoded_content = download.content.decode('ascii', 'ignore')
        # Extract data from CSV into list.
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        learner_profiles = list(cr)
    elif selection == "problems":
        print("Downloading and writing problem responses only.")

    if selection in ("both", "problems"):
        # Define parameters for extracting problem response data.
        problem_api_url = ("http://localhost:18100/api/v0/courses/"
                           "{}/reports/problem_response".format(course_id))
        headers = {"Authorization": "Token {}".format(hks_secret_token)}
        problem_data = requests.get(problem_api_url, headers=headers).json()
        problem_download_url = problem_data['download_url']
        # Download the CSV from download_url.
        with requests.Session() as s:
            download = s.get(problem_download_url)
        # Decode problem response data.
        decoded_content = download.content.decode('ascii', 'ignore')
        # Extract data from CSV into list.
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        problem_responses = list(cr)
    elif selection == "profiles":
        print("Downloading and writing learner profiles only.")

    # This section builds on Google quickstart template.
    # https://developers.google.com/sheets/api/quickstart/python
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

    if selection in ("both", "profiles"):
        learners_range = 'student_profile_info'
    if selection in ("both", "problems"):
        problem_range = 'problem_responses'
    if selection == "both":
        data = [
            {
                'range': learners_range,
                'values': learner_profiles
            },
            {
                'range': problem_range,
                'values': problem_responses
            }
        ]
    elif selection == "profiles":
        data = [
            {
                'range': learners_range,
                'values': learner_profiles
            }
        ]
    elif selection == "problems":
        data = [
            {
                'range': problem_range,
                'values': problem_responses
            }
        ]
    body = {'valueInputOption': 'RAW', 'data': data}
    result = service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheetId, body=body).execute()


def tunnel_and_write_to_g_sheet(dashboard):
    """Establish SSH tunnel, download data, and write to Google Sheet"""
    ssh()
    course = dashboard[0]
    sheet = dashboard[1]
    if len(dashboard) == 2:
        write_to_g_sheet(course, sheet)
    elif len(dashboard) == 3:
        selection = dashboard[2]
        write_to_g_sheet(course, sheet, selection)
    print("Upload to {} master sheet complete".format(sheet))

if __name__ == '__main__':
    dashboards = [
        ["AGG", "AGG"]
    ]

    for dashboard in dashboards:
        tunnel_and_write_to_g_sheet(dashboard)

    total_time = round((time.time() - start_time), 2)
    print("Total run time: {} seconds".format(total_time))
