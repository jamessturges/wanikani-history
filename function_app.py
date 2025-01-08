import logging
import http.client
import json
import os
from azure.storage.blob import BlobServiceClient
import azure.functions as func
from datetime import datetime, timezone
from jinja2 import Template

# WaniKani information
WANIKANI_BASE_URL = "api.wanikani.com"
WANIKANI_API_KEY = os.getenv("WANIKANI_API_KEY")

# Azure Blob Storage configuration
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER_NAME = "appdata"
BLOB_NAME = "wanikani_stats.json"

# Headers for API requests
HEADERS = {
    "Authorization": f"Bearer {WANIKANI_API_KEY}"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

app = func.FunctionApp()

# Run right before midnight
@app.timer_trigger(schedule="59 23 * * * *", arg_name="myTimer", run_on_startup=False,
                   use_monitor=False)
def write_to_blob_timer(myTimer: func.TimerRequest) -> None:
    try:
        write_to_blob()
        return func.HttpResponse("Data update triggered successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Failed to trigger data update. Error: {e}")
        return func.HttpResponse("Failed to trigger data update.", status_code=499)

@app.route(route="/write_to_blob", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def write_to_blob_trigger(req: func.HttpRequest) -> func.HttpResponse:
    try:
        write_to_blob()
        return func.HttpResponse("Data update triggered successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Failed to trigger data update. Error: {e}")
        return func.HttpResponse("Failed to trigger data update.", status_code=499)


def write_to_blob() -> None:
    try:
        logger.info("Timer triggered. Starting data fetch process...")
        logger.info(f"API KEY: {WANIKANI_API_KEY}")

        # Fetch data from WaniKani
        srs_totals = get_srs_totals()

        # Log final totals
        logger.info("All pages processed. Final SRS Stage Totals:")
        logger.info(f"Apprentice: {sum(srs_totals[i] for i in range(1, 5))}")
        logger.info(f"Guru: {sum(srs_totals[i] for i in range(5, 7))}")
        logger.info(f"Master: {srs_totals[7]}")
        logger.info(f"Enlightened: {srs_totals[8]}")
        logger.info(f"Burned: {srs_totals[9]}")

        # Fetch user level
        level = get_level()

        # Read existing data from the blob
        existing_data = read_blob()

        # Update data for today's date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing_data[today] = {
            "level": level,
            "apprentice": sum(srs_totals[i] for i in range(1, 5)),
            "guru": sum(srs_totals[i] for i in range(5, 7)),
            "master": srs_totals[7],
            "enlightened": srs_totals[8],
            "burned": srs_totals[9],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

        # Write updated data back to the blob
        write_blob(existing_data)

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)

def read_blob():
    """Read JSON data from Azure Blob Storage."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=BLOB_NAME)

        logger.info(f"Reading blob: {BLOB_NAME} from container: {BLOB_CONTAINER_NAME}")
        blob_data = blob_client.download_blob().readall()
        return json.loads(blob_data)
    except Exception as e:
        logger.warning(f"Blob not found or empty. Returning empty dictionary. Error: {e}")
        return {}

def write_blob(data):
    """Write JSON data to Azure Blob Storage."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        if not container_client.exists():
            container_client.create_container()
            logger.info(f"Created container: {BLOB_CONTAINER_NAME}")

        blob_client = container_client.get_blob_client(BLOB_NAME)

        logger.info(f"Writing blob: {BLOB_NAME} to container: {BLOB_CONTAINER_NAME}")

        blob_client.upload_blob(json.dumps(data, indent=4), overwrite=True)
        logger.info("Blob successfully written.")
    except Exception as e:
        logger.error(f"Failed to write blob. Error: {e}")

def get_level() -> int:
    """Fetch level from WaniKani API"""
    endpoint = "/v2/user"
    try:
        logger.info(f"Making API call to {WANIKANI_BASE_URL}{endpoint}")
        conn = http.client.HTTPSConnection(WANIKANI_BASE_URL)
        conn.request("GET", endpoint, headers=HEADERS)
        response = conn.getresponse()
        if response.status != 200:
            raise Exception(f"API call failed with status code {response.status}")
        data = json.loads(response.read().decode())
        level = data['data']['level']
        logger.info(f"User level fetched: {level}")
        return level
    except Exception as e:
        logger.error(f"Error while fetching user level: {e}", exc_info=True)
        raise

def get_srs_totals() -> dict:
    """Fetch SRS totals from WaniKani API."""
    srs_totals = {
        1: 0,  # Apprentice 1
        2: 0,  # Apprentice 2
        3: 0,  # Apprentice 3
        4: 0,  # Apprentice 4
        5: 0,  # Guru 1
        6: 0,  # Guru 2
        7: 0,  # Master
        8: 0,  # Enlightened
        9: 0   # Burned
    }

    next_url = "/v2/assignments"

    try:
        while next_url:
            logger.info(f"Making API call to {WANIKANI_BASE_URL}{next_url}")

            # Call the API
            conn = http.client.HTTPSConnection(WANIKANI_BASE_URL)
            conn.request("GET", next_url, headers=HEADERS)

            response = conn.getresponse()
            logger.info(f"Received response with status: {response.status}")
            if response.status != 200:
                logger.error(f"API call failed with status {response.status}: {response.reason}")
                raise Exception(f"API call failed with status {response.status}: {response.reason}")

            # Parse JSON response
            logger.info("Parsing API response...")
            data = json.loads(response.read().decode())
            conn.close()

            # Process the 'data' array
            logger.info(f"Processing {len(data['data'])} items from the current page...")
            for item in data["data"]:
                srs_stage = item["data"]["srs_stage"]
                if srs_stage in srs_totals:
                    srs_totals[srs_stage] += 1

            # Log current totals
            logger.info(f"Current totals by SRS stage: {srs_totals}")

            # Check if there's a next page
            next_url = data["pages"].get("next_url")
            if next_url:
                if next_url:
                    next_url = next_url.replace(f"https://{WANIKANI_BASE_URL}", "")
                logger.info(f"Next page URL: {next_url}")
            else:
                logger.info("No more pages to process.")
    except Exception as e:
        logger.error(f"Error while fetching or processing data: {e}", exc_info=True)
        raise

    return srs_totals

@app.route(route="/", auth_level=func.AuthLevel.ANONYMOUS)
def serve_website(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(f'Python HTTP trigger function processed a request from {req.url}')

    try:
        data = read_blob()
        dates = sorted(data.keys())  # Sort dates in ascending order

        if len(dates) < 2:
            return func.HttpResponse("Not enough data to compare.", status_code=200)

        def format_with_difference(current, previous):
            difference = current - previous
            return f"{current} ({difference:+d})"

        rows = []
        for i in range(1, len(dates)):
            current_date = dates[i]
            previous_date = dates[i - 1]

            current_totals = data[current_date]
            previous_totals = data[previous_date]

            level = current_totals['level']
            apprentice = format_with_difference(current_totals['apprentice'], previous_totals['apprentice'])
            guru = format_with_difference(current_totals['guru'], previous_totals['guru'])
            master = format_with_difference(current_totals['master'], previous_totals['master'])
            enlightened = format_with_difference(current_totals['enlightened'], previous_totals['enlightened'])
            burned = format_with_difference(current_totals['burned'], previous_totals['burned'])

            current_total = current_totals['apprentice'] + current_totals['guru'] + current_totals['master'] + current_totals['enlightened'] + current_totals['burned']
            previous_total = previous_totals['apprentice'] + previous_totals['guru'] + previous_totals['master'] + previous_totals['enlightened'] + previous_totals['burned']
            total = format_with_difference(current_total, previous_total)

            rows.append({
                "date": current_date,
                "level": level,
                "apprentice": apprentice,
                "guru": guru,
                "master": master,
                "enlightened": enlightened,
                "burned": burned,
                "total": total,
            })

        rows.reverse()  # Reverse the rows to display in descending order

        table_html = """
        <html>
        <head>
            <title>WaniKani History</title>
        </head>
        <body>
            <h1 style="display: inline;">WaniKani History</h1>
            <button style="margin-left: 10px;" onclick="triggerDataUpdate()">Update Data</button>
            <table border="1" style="margin-top: 10px;">
            <tr>
            <th>Date</th>
            <th>Level</th>
            <th>Apprentice</th>
            <th>Guru</th>
            <th>Master</th>
            <th>Enlightened</th>
            <th>Burned</th>
            <th>Total</th>
            </tr>
            {% for row in rows %}
            <tr>
            <td>{{ row.date }}</td>
            <td>{{ row.level }}</td>
            <td>{{ row.apprentice }}</td>
            <td>{{ row.guru }}</td>
            <td>{{ row.master }}</td>
            <td>{{ row.enlightened }}</td>
            <td>{{ row.burned }}</td>
            <td>{{ row.total }}</td>
            </tr>
            {% endfor %}
            </table>
            <script>
            function triggerDataUpdate() {
            fetch('/write_to_blob', {
            method: 'POST'
            })
            .then(response => {
            if (response.ok) {
                location.reload(); // Refresh the page
            } else {
                alert('Failed to trigger data update.');
            }
            })
            .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while triggering data update.');
            });
            }
            </script>
        </body>
        </html>
        """
        template = Template(table_html)
        rendered_html = template.render(rows=rows)
        return func.HttpResponse(rendered_html, mimetype="text/html")
    except Exception as e:
        logging.error(f"Failed to serve JSON as table. Error: {e}")
        return func.HttpResponse("An error occurred while serving the data.", status_code=500)