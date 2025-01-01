import logging
import http.client
import json
import os
from azure.storage.blob import BlobServiceClient
import azure.functions as func
from datetime import datetime, timezone

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

@app.timer_trigger(schedule="59 23 * * * *", arg_name="myTimer", run_on_startup=False,
                   use_monitor=False)
def write_to_json(myTimer: func.TimerRequest) -> None:
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

        # Read existing data from the blob
        existing_data = read_blob()

        # Update data for today's date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing_data[today] = {
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