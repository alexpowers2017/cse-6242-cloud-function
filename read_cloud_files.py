from google.cloud.storage import Client
import pandas as pd
import os



def get_all_blobs(storage_client):
    """ Returns a list of blobs, each one representing an individual file uploaded to our cloud storage bucket. """
    return [blob for blob in storage_client.list_blobs('national-park-reviews-cse-6242')]

def get_google_review_blobs(storage_client) -> list:
    """ Returns a list of 62 'blobs', each one representing a Google reviews csv file in google cloud storage. """
    return [blob for blob in get_all_blobs(storage_client) if 'national-park-reviews' in blob.name and 'csv' in blob.name]

def read_google_review_file(blob) -> tuple:
    """ Takes a blob and returns a tuple with a 4-letter park code and a list of strings, with each element as one
    non-empty text review. """
    park_code = blob.name.split('/')[1].replace('.csv', '')
    df = pd.read_csv(f'gs://{blob.bucket.name}/{blob.name}')
    reviews = [review for review in df['cleaned_review'].tolist() if not pd.isna(review)]
    return park_code, reviews

def read_all_google_reviews(storage_client, limit=62) -> dict:
    """ Reads all the Google review csv files from cloud storage and returns a dictionary where the keys are 4-letter
    park codes and the value is a long string of all non-empty text reviews. """
    reviews_dict = {}
    for blob in get_google_review_blobs(storage_client)[:limit]:
        park_code, reviews = read_google_review_file(blob)
        reviews_dict[park_code] = ' '.join(reviews)
    return reviews_dict

def get_wikipedia_blobs(storage_client) -> list:
    """ Returns a list of 62 'blobs', each one representing a wikipedia page txt file in google cloud storage. """
    return [blob for blob in get_all_blobs(storage_client) if 'wikipedia-pages' in blob.name and 'txt' in blob.name]

def read_wiki_page(blob) -> tuple:
    """ Takes a blob and returns a tuple, with a 4-letter park code and a long string with the text of a wiki page. """
    park_code = blob.name.split('/')[1].replace('.txt', '')
    page_text = blob.download_as_text()
    return park_code, page_text

def read_all_wiki_pages(storage_client, limit=62) -> dict:
    """ Reads all the Wikipedia txt files from cloud storage and returns a dictionary where the keys are 4-letter
     park codes and the values are long strings with the full text of a wiki page. """
    wiki_dict = {}
    for blob in get_wikipedia_blobs(storage_client)[:limit]:
        park_code, page_text = read_wiki_page(blob)
        wiki_dict[park_code] = page_text
    return wiki_dict



  
