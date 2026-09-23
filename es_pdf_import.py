import pymupdf
import base64
import httpx
from openai import OpenAI, DefaultHttpxClient
import requests
from pathlib import Path
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import click

# updated from CLI
ES_HOST = ""
ES_APIKEY = ""

# EIS models
ES_OCR_MODEL = ".jina-ocr-v1-chat_completion"
ES_SEMANTIC_MODEL = ".jina-embeddings-v5-text-small"

# convert openai conventions to ES conventions
def update_base_url(request: httpx.Request) -> None:
    request.headers["Authorization"] = f"ApiKey {ES_APIKEY}"
    request.url = request.url.copy_with(path=f"/_inference/chat_completion/{ES_OCR_MODEL}")

# setup es index
def init_es(es_host, es_apikey, es_index, version, clean=False):
    mappings = {
        "mappings": {
            "properties": {
                "title": {
                    "inference_id": ES_SEMANTIC_MODEL,
                    "type": "semantic_text"
                },
                "page": {
                    "type": "long"
                },
                "body": {
                    "inference_id": ES_SEMANTIC_MODEL,
                    "type": "semantic_text"
                },
                "version": {
                    "type": "keyword"
                }
            }
        }
    }

    # delete old index
    if clean:
        resp = requests.delete(f"{es_host}/{es_index}",
                            headers={"Content-Type": "application/json", "Authorization": f"ApiKey {es_apikey}"})
        print(resp.json())

    # create new index
    resp = requests.put(f"{es_host}/{es_index}",
                        json=mappings,
                        headers={"Content-Type": "application/json", "Authorization": f"ApiKey {es_apikey}"})
    print(resp.json())

    # delete old version docs
    old_version = {
        "query": {
            "bool": {
                "must_not": [
                    {
                        "term": {
                            "version.keyword": version
                        }
                    }
                ]
            }
        }
    }
    resp = requests.post(f"{es_host}/{es_index}/_delete_by_query",
                        json=old_version,
                        headers={"Content-Type": "application/json", "Authorization": f"ApiKey {es_apikey}"})
    print(resp.json())

def ingest_pdf(es_host, es_apikey, es_index, input, version):

    # use OpenAI client to handle EIS chat_completion streaming endpoint
    apiclient = OpenAI(
        api_key=es_apikey,
        base_url= es_host,
        http_client=DefaultHttpxClient(
            event_hooks={
                "request": [update_base_url],
            }
        ),
    )

    # handle EIS throttling
    retry_strategy = Retry(
        total=5,                  # Total number of attempts to make
        backoff_factor=1,         # Wait time multiplier (see Backoff Logic below)
        status_forcelist=[408, 429, 500, 502, 503, 504],  # HTTP status codes to retry on
        allowed_methods=["GET", "HEAD", "OPTIONS"],       # Only retry idempotent methods
        respect_retry_after_header=True                  # Honor 'Retry-After' headers if present
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Open the PDF document
    doc = pymupdf.open(input)
    
    # Iterate through every page
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)  # Load the specific page
        pix = page.get_pixmap()         # Render the page to an image (pixmap)

        # to base64
        image_bytes = pix.tobytes("png")
        base64_bytes = base64.b64encode(image_bytes)
        base64_string = base64_bytes.decode("utf-8")

        # OCR to markdown via EIS
        completion = apiclient.chat.completions.create(
            model="jina-ocr-v1",
            messages=[
                    {
                        "role": "user",
                        "content": [{
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_string}"},
                        }]
                    }
                ]
        )
        completion_content = completion.choices[0].message.content

        # create the es doc
        es_doc = {
            "title": Path(input).stem,
            "version": version,
            "page": page_num,
            "body": completion_content
        }

        # create an ID appropriate for updating
        doc_id_string = f"{Path(input).stem}-{version}-{str(page_num)}".encode('utf-8')
        doc_id_hash = hashlib.sha256(doc_id_string).hexdigest()

        # post the doc and semantically encode title and body
        try:
            resp = session.post(f"{es_host}/{es_index}/_doc/{doc_id_hash}",
                json=es_doc,
                headers={"Content-Type": "application/json", "Authorization": f"ApiKey {es_apikey}"})
            print(page_num)
            print(resp.json())
        except requests.exceptions.RequestException as e:
            print(f"Request failed after all retries. Error: {e}")

@click.command()
@click.option('--es_host', default="", help='url of es')
@click.option('--es_apikey', default="", help='es api key')
@click.option('--es_index', default="", help='es index')
@click.option('--input', default="", help='input pdf file')
@click.option('--version', default="v1", help='doc version')
@click.option('--clean', default=False, help='delete existing index')
def main(es_host, es_apikey, es_index, input, version, clean):
    global ES_HOST 
    global ES_APIKEY

    ES_HOST = es_host
    ES_APIKEY = es_apikey

    init_es(es_host, es_apikey, es_index, version, clean)
    ingest_pdf(es_host, es_apikey, es_index, input, version)

if __name__ == "__main__":
    main()
