import azure.functions as func
import logging
import json
import tempfile
import subprocess
from azure.storage.blob import BlobServiceClient
import os

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

AZURE_CONNECTION_STRING = os.getenv('AZURE_CONNECTION_STRING')
INPUT_CONTAINER = os.getenv('INPUT_CONTAINER')
OUTPUT_CONTAINER = os.getenv('OUTPUT_CONTAINER')
BLOB_SERVICE_CLIENT = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

@app.route(route="clear")
def clear(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )

@app.route(route="remove_background", auth_level=func.AuthLevel.ANONYMOUS)
def remove_background(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    data = req.get_json()
    blob_name = data.get('blob_name')
    print(data)
    if not blob_name:
        return func.HttpResponse(
            json.dumps({'error': 'No blob name provided'}),
             status_code=400,
             mimetype='application/json'
        )
    
    try:
        # Determine the temp directory
        temp_dir = tempfile.gettempdir()

        # Ensure the temp directory exists
        os.makedirs(temp_dir, exist_ok=True)

        # Download the image from Azure Blob Storage
        input_blob_client = BLOB_SERVICE_CLIENT.get_blob_client(container=INPUT_CONTAINER, blob=blob_name)
        download_file_path = os.path.join(temp_dir, blob_name)
        
        with open(download_file_path, "wb") as download_file:
            download_file.write(input_blob_client.download_blob().readall())
        
        # Execute the external command to remove the background with the --dest parameter
        command = f'transparent-background --source {download_file_path} --dest {temp_dir}'
        subprocess.run(command, shell=True, check=True)

        # Determine the output file name
        output_file_name = f"{os.path.splitext(blob_name)[0]}_rgba.png"
        output_file_path = os.path.join(temp_dir, output_file_name)

        # Upload the processed image back to Azure Blob Storage
        output_blob_client = BLOB_SERVICE_CLIENT.get_blob_client(container=OUTPUT_CONTAINER, blob=output_file_name)
        
        with open(output_file_path, "rb") as upload_file:
            output_blob_client.upload_blob(upload_file, overwrite=True)
        
        # Clean up the temp files manually
        os.remove(download_file_path)
        os.remove(output_file_path)

        return func.HttpResponse(
             json.dumps({'message': 'Background removed and image saved successfully'}),
             status_code=200,
             mimetype='application/json'
        )


    except subprocess.CalledProcessError as e:
        return func.HttpResponse(
             json.dumps({'error': 'Command failed', 'output': str(e)}),
             status_code=500,
             mimetype='application/json'
        )
    except Exception as e:
        return func.HttpResponse(
             json.dumps({'error': str(e)}),
             status_code=500,
             mimetype='application/json'
        )
