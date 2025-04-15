# Imports
from typing import Union
import pandas as pd
from geopy.distance import geodesic # Required for def calculate_distance_to_parks()
from google.cloud.storage import Client
from read_cloud_files import read_all_google_reviews, read_all_wiki_pages
from cosine_similarity import compute_query_similarity


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 70)
pd.set_option('display.width', None)


def recommend_parks(prompt: str, month: int, crowd_preference: Union[int,str], city: str, limit: int):
    """ The main function that takes in the user's input and returns a dataframe, sorted from highest to lowest recommendation score. """
    # Make sure we're authenticated with Google cloud storage
    client = Client()

    wikipedia_df = calculate_prompt_wikipedia_similarity_scores(prompt, client)
    reviews_df = calculate_prompt_review_similarity_scores(prompt, client)
    crowd_df = get_traffic_score(month=month, crowd_preference=crowd_preference)
    counts_df = load_and_assign_google_weights()
    ignore_crowd = crowd_preference == 'null'

    weighted_score = calculate_weighted_score(
        wikipedia_df=wikipedia_df,
        reviews_df=reviews_df,
        crowd_df=crowd_df,
        counts_df=counts_df,
        ignore_crowd=ignore_crowd
    )

    distance_df = calculate_distance_to_parks(city)
    full_df = weighted_score.merge(distance_df, on='Code', how='left')
    full_df.drop('GoogleWeight', axis=1, inplace=True)
    full_df_sorted = full_df.sort_values(by='WeightedScore', ascending=False)
    full_df_top_n = full_df_sorted.head(limit).copy()
    full_df_top_n.rename(columns={
        'Code': 'code',
        'WikiScore': 'wikipediaScore',
        'ReviewScore': 'reviewScore',
        'CrowdDensityScore': 'crowdScore',
        'WeightedScore': 'score',
        'Distance_miles': 'distanceMiles'
    }, inplace=True)
    #return full_df_top_n
    return full_df_top_n.to_dict(orient='records')


def calculate_prompt_review_similarity_scores(prompt: str, client):
    """ Given a prompt, calculate the prompt's similarity to the Google reviews and return the score for each park as a dataframe. """
    google_reviews = read_all_google_reviews(client)
    return compute_query_similarity(prompt, google_reviews)


def calculate_prompt_wikipedia_similarity_scores(prompt: str, client):
    """ Given a prompt, calculate the prompt's similarity to the Wikipedia pages and return the score for each park as a dataframe. """
    wiki_pages = read_all_wiki_pages(client)
    return compute_query_similarity(prompt, wiki_pages)


def get_traffic_score(month, crowd_preference):
    """
    Get the crowd density score using the user's input and a lookup csv file in cloud storage.
    
    :param month: number 1-12 representing the month the trip is happening
    :param crowd_preference: 0/1 flag representing whether the user wants to go at busy times.
        0 - 'I want to avoid crowds.'
        1 - 'I want to go at the most popular times.'
    :return: Pandas dataframe with the crowd density scores for each park, according to the user's preference.
        'Code' - 4-letter park code
        'CrowdDensityScore' - a score between 0 and 1 showing how closely the park aligns with the user's preferences
        in the month they've chosen to travel.
    """
    all_traffic_indices = pd.read_csv('gs://national-park-reviews-cse-6242/traffic_indices.csv')
    matching_months = all_traffic_indices[all_traffic_indices['month'] ==  int(month)].copy()
    try:
        crowd_preference_int = int(crowd_preference)
        if crowd_preference_int == 0:
            matching_months['CrowdDensityScore'] = 1 - matching_months['traffic_index']
        else:
            matching_months['CrowdDensityScore'] = matching_months['traffic_index']
    except:
        matching_months['CrowdDensityScore'] = matching_months['traffic_index']

    return matching_months[['Code', 'CrowdDensityScore']]

def load_and_assign_google_weights():
    """
    Add 'GoogleWeight' column to the DataFrame based on the quartile of GoogleReviewCount.

    Quartile Ranges:
    - 0–25th percentile  → weight = 0.2
    - 25–50th percentile → weight = 0.3
    - 50–75th percentile → weight = 0.5
    - 75–100th percentile→ weight = 0.6

    0.2 is left over for default crowd density weight

    Returns:
    - pd.DataFrame: Original DataFrame with an added 'GoogleWeight' column.
    """

    df = pd.read_csv('gs://national-park-reviews-cse-6242/parkcode_googreviewcount.csv')

    # Remove commas and convert to int
    df['GoogleReviewCount'] = df['GoogleReviewCount'].str.replace(',', '', regex=False).astype(int)

    # Compute quartiles
    q1 = df['GoogleReviewCount'].quantile(0.25)
    q2 = df['GoogleReviewCount'].quantile(0.50)
    q3 = df['GoogleReviewCount'].quantile(0.75)

    # Function to assign weights based on quartiles
    def get_weight(count):
        if count <= q1:
            return 0.2
        elif count <= q2:
            return 0.3
        elif count <= q3:
            return 0.5
        else:
            return 0.6

    # Apply weight function
    df['GoogleWeight'] = df['GoogleReviewCount'].apply(get_weight)

    return df

def calculate_weighted_score(wikipedia_df: pd.DataFrame, reviews_df: pd.DataFrame, crowd_df: pd.DataFrame, counts_df: pd.DataFrame, ignore_crowd: bool) -> pd.DataFrame:
    """
    Calculate a weighted average score for a national park based on review scores, Wikipedia presence, and crowd density.

    Parameters:
    - wikipedia_df (pd.DataFrame): DataFrame with columns ['Code', 'Name', 'Similarity']
    - reviews_df (pd.DataFrame): DataFrame with columns ['Code', 'Name', 'Similarity']
    - crowd_df (pd.DataFrame): DataFrame with columns ['Code', 'CrowdDensityScore']
    - counts_df (pd.DataFrame): DataFrame with columns ['Code', 'GoogleReviewCount', 'GoogleWeight']

    Returns:
    - pd.DataFrame: A DataFrame with columns ['Park Code', 'WeightedScore'] for each park.
    """

    #### Code to clean up dfs from score output and crowd output #######
    # Rename columns before merging
    wikipedia_df = wikipedia_df.rename(columns={'Similarity': 'WikiScore'})
    reviews_df = reviews_df.rename(columns={'Similarity': 'ReviewScore'})
    counts_df = counts_df.rename(columns={'Park Code': 'Code'})  # So it aligns with others

    # Merge all data sources on 'Code'
    merged_df = (
        wikipedia_df
        .merge(reviews_df[['Code', 'ReviewScore']], on='Code', how='left')
        .merge(crowd_df[['Code', 'CrowdDensityScore']], on='Code', how='left')
        .merge(counts_df[['Code', 'GoogleWeight']], on='Code', how='left')
    )

    # Function to calculate weighted score per park
    def calc_score(row):
        # Extract the individual scores
        review_score = row['ReviewScore']
        wiki_score = row['WikiScore']
        crowd_score = row['CrowdDensityScore']
        review_weight = row['GoogleWeight']

        # Calculate weights for each score type based on GoogleWeight
        wiki_weight = 0.8 - review_weight
        crowd_weight = 0.2 if not ignore_crowd else 0

        # Normalize weights so they sum to 1 (they are proportional)
        total_weight = review_weight + wiki_weight + crowd_weight
        review_weight /= total_weight
        wiki_weight /= total_weight
        crowd_weight /= total_weight

        # Compute the weighted average score
        weighted_score = (
            review_score * review_weight +
            wiki_score * wiki_weight +
            crowd_score * crowd_weight
        )
        return round(weighted_score, 3)

    # Apply the score calculation to each row in the merged DataFrame
    merged_df['WeightedScore'] = merged_df.apply(calc_score, axis=1)

    return merged_df
    # Return only the 'Code' and 'WeightedScore' columns in the result
    #return merged_df[['Code', 'WeightedScore']]

def calculate_distance_to_parks(city_name: str): # Switch if inputs for cities_df, parks_df do not exist
  """
  Takes city_name and calculates distance in miles to all parks (62 - Kings and Sequoia National Park both under 'seki' park code, so distance will be the same).
  Returns dataframe 62 x 3 columns - Park Name, Park Code, Distance_miles
  Code assumes no inputs for parks_df, cities_df. Code will load csv files from Google cloud storage.
  
  Parameters:
    city_name: The city name as defined in the worldcities_data (to be selected from dropdown in user input).

  Returns:
    distances_df: Dataframe of shape 62 x 3 (columns = Park Name, Park Code, Distance_miles), sorted by ascending order.
  """
  # # Include if assuming csv not loaded globally
  cities_df = pd.read_csv("gs://national-park-reviews-cse-6242/worldcities_data.csv") # Change CSV file path as required
  parks_df = pd.read_csv("gs://national-park-reviews-cse-6242/parks_03132025.csv") # Change CSV file path as required

  # Ensure city_name is in cities_csv or cities_df
  try:
    city = cities_df[cities_df["City_Country"] == city_name]  # Sub cities_csv for cities_df if required
  except:
    raise ValueError(f"{city_name} not found in the cities list.")

  # Get city coordinates
  city_lat, city_lon = city.iloc[0]['lat'], city.iloc[0]['lng']

  # Calculate distances from city to each park
  distances = []
  for _, row in parks_df.iterrows():
      park_lat, park_lon = row['Latitude'], row['Longitude']
      distance_miles = geodesic((city_lat, city_lon), (park_lat, park_lon)).miles
      distances.append({'Code': row['Park Code'], 'Distance_miles': round(distance_miles, 2)})

  # Convert list of distances to DataFrame
  distances_df = pd.DataFrame(distances)

  # Sort distances in ascending order
  distances_df = distances_df.sort_values(by='Distance_miles', ascending=True)

  # Return dataframe
  return distances_df # returns dataframe of shape 62 x 2 (columns = Code, Distance_miles). 62 total rows (not 63) as in NPS data Kings and Sequoia National Park are consider one and labeled as 'seki' Park Code.

def get_proximities(park_code: str):
  """
  Given a Park Code, return a dataframe with distance from other parks, sorted by ascending distances.

  Parameter:
    park_code: Park code for specific park.

  Return:
    proximities: Dataframe containing distances (in miles) of parks from selected park, sorted by ascending order, excluding selected park. Shape 61,2 (columns = Park Code and selected park_code) (if select park removed). 
  """
  # Uncomment if park_proximities not loaded globally
  park_proximities = pd.read_csv('gs://national-park-reviews-cse-6242/park_proximities_miles.csv')

  # Ensure park_code is in list of parks, if not return error statement
  if park_code not in list(park_proximities['Park Code']):
          return f"Error: Park code '{park_code}' not found in dataset."

  # Extract column for the given park and sort values by distance in ascending order (closest park first)
  sorted_distances = park_proximities[['Park Code', park_code]].sort_values(by=park_code)

  # Drop first row - should be selected park distance to self = 0
  final_df = sorted_distances.drop(0, axis=0)
  
  return final_df # Returns dataframe of shape 61,2
