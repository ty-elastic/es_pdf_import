# Elasticsearch PDF Import Tool

This is a simple python app that will accept a PDF and:

1) turn it into a set of images per page (this is required by the `jina-ocr-v1-chat_completion` model)
2) for each image, run it through an EIS-hosted `jina-ocr-v1-chat_completion` model to derive markdown
3) insert each page (as markdown) as an Elasticsearch document in an index of your choosing, with semantically encoded content fields (using the EIS-hosted `jina-embeddings-v5-text-small` model)

# Requirements

* Elastic Cloud Hosted or Serverless cluster or project with EIS enabled
* Docker, Podman, or python

# Run it

```bash
export ES_URL="..." # the URL of your Elastic Cloud Hosted or Serverless deployment
export ES_APIKEY="..." # an API key associated with your deployment
export ES_INDEX="..." # the name of the index to import docs into
export PATH_TO_PDF="$PWD/..." # the local path to the PDF

docker run -v $PATH_TO_PDF:/input.pdf \     
    us-central1-docker.pkg.dev/elastic-sa/tbekiares/es_pdf_import \
    --es_host $ES_URL \
    --es_apikey $ES_APIKEY \
    --es_index $ES_INDEX \
    --input "/input.pdf"
```

# Debug it
```bash
export ES_URL="..." # the URL of your Elastic Cloud Hosted or Serverless deployment
export ES_APIKEY="..." # an API key associated with your deployment
export ES_INDEX="..." # the name of the index to import docs into
export PATH_TO_PDF="$PWD/..." # the local path to the PDF

uv pip install -r requirements.txt
uv run es_pdf_import.py \
    --es_host $ES_URL \
    --es_apikey $ES_APIKEY \
    --es_index $ES_INDEX \
    --input "/input.pdf"
```
