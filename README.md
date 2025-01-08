# WaniKani History Function App

This Azure Function App fetches and displays WaniKani SRS stage totals and user level history. It stores the data in Azure Blob Storage and serves a web page to display the history.

## Features

- Fetches SRS stage totals and user level from the WaniKani API.
- Stores the data in Azure Blob Storage.
- Serves a web page to display the history with daily comparisons.
- Allows manual data updates via a button on the web page.

## Prerequisites

- Azure account
- WaniKani API key
- Azure Blob Storage account

## Setup

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/wanikani-history.git
    cd wanikani-history
    ```
2. **Deploy to Azure**:
    - Use the Azure CLI or Visual Studio Code to deploy the Function App to Azure. Make sure to set the following environment variables:
       - WANIKANI_API_KEY=your_wanikani_api_key
       - BLOB_CONNECTION_STRING=your_blob_connection_string 

## Usage

- Access the web page at `https://yourfunctionapp.azurewebsites.net` to view the WaniKani history.
- Click the "Update Data" button to manually trigger a data update in cases where you don't want to wait until end of day.

## File Structure

- function_app.py: Main function app code.
- requirements.txt: Python dependencies.
- host.json: Azure Functions host configuration.
- local.settings.json: Local settings for Azure Functions.

## Functions

### `write_to_blob`

Fetches SRS stage totals and user level from the WaniKani API and writes the data to Azure Blob Storage.

### `read_blob`

Reads JSON data from Azure Blob Storage.

### `serve_website`

Serves a web page to display the WaniKani history with daily comparisons.

### `write_to_blob_timer`

Timer trigger to manually trigger the `write_to_blob` function.

### `write_to_blob_trigger`

HTTP trigger to manually trigger the `write_to_blob` function.
