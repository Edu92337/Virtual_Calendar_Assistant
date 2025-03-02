import openai
import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
from datetime import timedelta
import pytz
from dotenv import load_dotenv
import os


load_dotenv()


api_key = os.environ.get('OPENAI_API_KEY')
client = openai.Client(api_key=api_key)


credentials_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
credentials = service_account.Credentials.from_service_account_file(
    credentials_path,
    scopes=['https://www.googleapis.com/auth/calendar']
)


def get_current_date():
    """Returns the current date in YYYY-MM-DD format."""
    data = datetime.datetime.date(datetime.datetime.now())
    return str(data)

def find_event_id(date_time, calendar_id='primary'):
    """
    Finds the ID of an event on Google Calendar based on the provided date and time.

    Parameters:
    - date_time: str - The date and time of the event in ISO 8601 format.
    - calendar_id: str - The ID of the calendar to search (default is 'primary').

    Returns:
    - str - The event ID if found, otherwise a message indicating no event was found.
    """
    try:
        date_time = datetime.datetime.fromisoformat(date_time)
    except ValueError:
        return "Invalid date/time format. Please use ISO 8601 format."

    service = build('calendar', 'v3', credentials=credentials)
    time_min = date_time.isoformat() + "Z"
    time_max = (date_time + datetime.timedelta(minutes=1)).isoformat() + "Z"

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
    except Exception as e:
        return f"Error accessing Google Calendar: {e}"

    events = events_result.get('items', [])
    return events[0]['id'] if events else "No event found at this time."

def check_google_calendar_event(date_time, calendar_id='primary', duration_hours=1):
    """
    Checks if a specific time slot is available on Google Calendar.

    Parameters:
    - date_time: datetime.datetime - The date and time to check.
    - calendar_id: str - The ID of the calendar to check (default is 'primary').
    - duration_hours: int - The duration of the event in hours (default is 1).

    Returns:
    - str - A message indicating whether the time slot is available or busy.
    """
    service = build('calendar', 'v3', credentials=credentials)
    time_min = date_time.astimezone(datetime.timezone.utc).isoformat()
    time_max = (date_time + datetime.timedelta(hours=duration_hours)).astimezone(datetime.timezone.utc).isoformat()

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": calendar_id}]
    }

    try:
        freebusy_result = service.freebusy().query(body=body).execute()
        busy_periods = freebusy_result['calendars'][calendar_id].get('busy', [])
        return 'Time slot is busy.' if busy_periods else 'Time slot is available.'
    except Exception as e:
        return f"Error checking availability: {e}"

def schedule_google_calendar_event(date_time, title, description, calendar_id='primary'):
    """
    Schedules an event on Google Calendar.

    Parameters:
    - date_time: datetime.datetime - The date and time of the event.
    - title: str - The title of the event.
    - description: str - Additional details about the event.
    - calendar_id: str - The ID of the calendar to schedule the event (default is 'primary').

    Returns:
    - str - A message indicating the status of the scheduling.
    """
    if check_google_calendar_event(date_time) == "Time slot is busy.":
        return "Cannot schedule. The time slot is already occupied."

    start_time = date_time.isoformat()
    end_time = (date_time + timedelta(hours=1)).isoformat()

    event = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/Sao_Paulo',
        },
    }

    try:
        service = build('calendar', 'v3', credentials=credentials)
        service.events().insert(calendarId=calendar_id, body=event).execute()
        return "Event scheduled successfully!"
    except Exception as e:
        return f"Error scheduling event: {e}"

def remove_google_calendar_event(event_id, calendar_id='primary'):
    """
    Removes an event from Google Calendar.

    Parameters:
    - event_id: str - The ID of the event to remove.
    - calendar_id: str - The ID of the calendar where the event is located (default is 'primary').

    Returns:
    - str - A message indicating the status of the removal.
    """
    try:
        service = build('calendar', 'v3', credentials=credentials)
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return f"Event with ID {event_id} has been successfully removed."
    except Exception as e:
        return f"Error removing event: {e}"


prompt = """
You are a virtual assistant capable of scheduling, removing, and checking appointments on a Google Calendar. Respond politely and professionally, using complete sentences and a friendly tone.

Before making any function calls, follow these steps to ensure the request is handled accurately and efficiently:

1. **Context Analysis**:
   - Verify if the user has provided all necessary information for scheduling, such as date, time, and event details.
   - If there is any ambiguity in the date or time, ask the user for clarification.

2. **Data Validation**:
   - Ensure the provided data is valid (e.g., correct date and time format).
   - Check for scheduling conflicts using the `check_google_calendar_event` function.

3. **Missing Data**:
   - If any required information is missing (e.g., event title), politely ask the user to provide it.

4. **Availability Check**:
   - Use the `check_google_calendar_event` function to verify if the requested time slot is available.
   - If the slot is unavailable, inform the user and suggest alternative times.

5. **Confirmation**:
   - Confirm all details with the user before proceeding with scheduling or removal.

6. **Function Calls**:
   - After confirming the details, use the appropriate function (`schedule_google_calendar_event`, `remove_google_calendar_event`, or `check_google_calendar_event`) to complete the task.

**Notes**:
- Never send incomplete or null data to the functions.
- Always clarify ambiguous requests before proceeding.
"""

mensagens = [
    {
        "role": "system",
        "content": prompt
    }
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "schedule_google_calendar_event",
            "description": "Schedules an event on Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_time": {
                        "type": "string",
                        "description": "The date and time of the event in ISO 8601 format."
                    },
                    "title": {
                        "type": "string",
                        "description": "The title of the event."
                    },
                    "description": {
                        "type": "string",
                        "description": "Additional details about the event."
                    }
                },
                "required": ["date_time", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_google_calendar_event",
            "description": "Removes an event from Google Calendar based on the event ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to be removed."
                    }
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_google_calendar_event",
            "description": "Checks if a specific time slot is available on Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_time": {
                        "type": "string",
                        "description": "The date and time to check in ISO 8601 format."
                    }
                },
                "required": ["date_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Returns the current date in YYYY-MM-DD format."
        }
    }
]

def generate_response(messages):
    response = client.chat.completions.create(
        messages=messages,
        model='gpt-4',
        max_tokens=1000,
        temperature=0,
        tools=tools,
        tool_choice="auto"
    )

    message_response = response.choices[0].message
    tool_calls = message_response.tool_calls

    if tool_calls:
        available_functions = {
            "schedule_google_calendar_event": schedule_google_calendar_event,
            "remove_google_calendar_event": remove_google_calendar_event,
            "check_google_calendar_event": check_google_calendar_event,
            "get_current_date": get_current_date
        }

        messages.append(message_response)

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)

            if function_name == "schedule_google_calendar_event":
                function_response = function_to_call(
                    date_time=datetime.datetime.fromisoformat(function_args.get("date_time")),
                    title=function_args.get("title"),
                    description=function_args.get("description", "")
                )
            elif function_name == "remove_google_calendar_event":
                function_response = function_to_call(
                    event_id=function_args.get("event_id")
                )
            elif function_name == "check_google_calendar_event":
                function_response = function_to_call(
                    date_time=datetime.datetime.fromisoformat(function_args.get("date_time"))
                )
            elif function_name == "get_current_date":
                function_response = function_to_call()

            if function_response:
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                })

        second_response = client.chat.completions.create(
            messages=messages,
            model='gpt-4',
            max_tokens=1000,
            temperature=0,
            tools=tools,
            tool_choice="auto"
        )
        return second_response.choices[0].message.content

    return response.choices[0].message.content


def start_conversation():
    print("Chatbot started! Type your questions or 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            print("Chatbot ended. Goodbye!")
            break

        mensagens.append({"role": "user", "content": user_input})
        final_response = generate_response(mensagens)
        mensagens.append({"role": "assistant", "content": final_response})
        print(f"Assistant: {final_response}")

if __name__ == '__main__':
    start_conversation()
