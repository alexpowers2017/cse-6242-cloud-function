# Imports
import pandas as pd
from geopy.distance import geodesic # Required for def calculate_distance_to_parks()

# In this file, we can write individual python functions to be used in the main file

# I sketched out a few of the functions that I think would be necessary and what I think the inputs and outputs would look like.
# This is can all be changed and adjusted according to everyone's thoughts

def recommend_parks(prompt: str, month: int, crowdPreference: int):
  """ The main function that takes in the user's input and returns a dataframe, sorted from highest to lowest recommendation score. """
  pass

def calculate_prompt_review_similarity_scores(prompt: str):
  """ Given a prompt, calculate the prompt's similarity to the google reviews and return the score for each park as a dataframe. """
  pass

def calculate_prompt_wikipedia_similarity_scores(prompt: str):
  """ Given a prompt, calculate the prompt's similarity to the Wikipedia pages and return the score for each park as a dataframe. """
  pass

def calculate_crowd_scores(month: int, crowdPreference: int):
  """ Given a month as a number 1-12 and a crowdPreference value 0 or 1, look up the park-specific crowd index for each park for the given month. """
  pass

def load_and_assign_google_weights(csv_path):
    """
    Add 'GoogleWeight' column to the DataFrame based on the quartile of GoogleReviewCount.

    Quartile Ranges:
    - 0–25th percentile  → weight = 0.2
    - 25–50th percentile → weight = 0.3
    - 50–75th percentile → weight = 0.5
    - 75–100th percentile→ weight = 0.6

    0.2 is left over for default crowd density weight

    Parameters:
    - csv_path (str): Path to CSV file with 'Code' and 'GoogleReviewCount' columns.

    Returns:
    - pd.DataFrame: Original DataFrame with an added 'GoogleWeight' column.
    """

    df = pd.read_csv(csv_path)

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

def calculate_weighted_score(wikipedia_df: pd.DataFrame, reviews_df: pd.DataFrame, crowd_df: pd.DataFrame, counts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate a weighted average score for a national park based on review scores, Wikipedia presence, and crowd density.

    Parameters:
    - wikipedia_df (pd.DataFrame): DataFrame with columns ['Park Name', 'Similarity Score', 'Park Code']
    - reviews_df (pd.DataFrame): DataFrame with columns ['Park Name', 'Similarity Score', 'Park Code']
    - crowd_df (pd.DataFrame): DataFrame with columns ['Park Code', 'CrowdScore']
    - counts_df (pd.DataFrame): DataFrame with columns ['Park Code', 'CrowdDensityScore', 'GoogleWeight']

    Returns:
    - pd.DataFrame: A DataFrame with columns ['Park Code', 'WeightedScore'] for each park.
    """

    #### Code to clean up dfs from score output and crowd output #######
    # Rename columns for standardization (if necessary) before merging
    wikipedia_df = wikipedia_df.rename(columns={'Similarity Score': 'WikiScore', 'Park Code': 'Code'})
    reviews_df = reviews_df.rename(columns={'Similarity Score': 'ReviewScore', 'Park Code': 'Code'})
    crowd_df = crowd_df.rename(columns={'CrowdScore': 'CrowdScore', 'Park Code': 'Code'})

    # Merge all data sources on 'Code' (Park Code)
    merged_df = (
        wikipedia_df
        .merge(reviews_df, on='Code', how='left')
        .merge(crowd_df, on='Code', how='left')
        .merge(counts_df, on='Code', how='left')
    )

    # Function to calculate weighted score per park
    def calc_score(row):
        # Extract the individual scores
        review_score = row['ReviewScore']
        wiki_score = row['WikiScore']
        crowd_score = row['CrowdScore']
        review_weight = row['GoogleWeight']

        # Calculate weights for each score type based on GoogleWeight
        wiki_weight = 0.8 - review_weight
        crowd_weight = 0.2

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
        return round(weighted_score, 2)

    # Apply the score calculation to each row in the merged DataFrame
    merged_df['WeightedScore'] = merged_df.apply(calc_score, axis=1)

    # Return only the 'Code' and 'WeightedScore' columns in the result
    return merged_df[['Code', 'WeightedScore']]

def calculate_distance_to_parks(city_name: str, cities_df, parks_df): # Switch if inputs for cities_df, parks_df do not exist
  """
  Takes city_name, cities_df, and parks_df and calculates distance in miles to all parks (62 - Kings and Sequoia National Park both under 'seki' park code, so distance will be the same).
  Returns dataframe 62 x 3 columns - Park Name, Park Code, Distance_miles
  Code assumes no inputs for parks_df, cities_df. Code will load csv files from a local file path.

  cities_df = Dataframe with city names, latitude, longitude, and 'City_Country' (for further differentiation)
  parks_df = Dataframe with park name, park code, latitude, longitude data
  
  Parameters:
    city_name: The city name as defined in the worldcities_data (to be selected from dropdown in user input).

  Returns:
    distances_df: Dataframe of shape 62 x 3 (columns = Park Name, Park Code, Distance_miles), sorted by ascending order.
  """
  # # Include if assuming csv not loaded globally
  # cities_df = pd.read_csv("../worldcities_data.csv") # Change CSV file path as required
  # parks_df = pd.read_csv("../parks_03132025.csv") # Change CSV file path as required

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
      distances.append({'Park Name': row['Park Name'], 'Park Code': row['Park Code'], 'Distance_miles': round(distance_miles, 2)})

  # Convert list of distances to DataFrame
  distances_df = pd.DataFrame(distances)

  # Sort distances in ascending order
  distances_df = distances_df.sort_values(by='Distance_miles', ascending=True)

  # Return dataframe
  return distances_df # returns dataframe of shape 62 x 3 (columns = Park Name, Park Code, Distance_miles). 62 total rows (not 63) as in NPS data Kings and Sequoia National Park are consider one and labeled as 'seki' Park Code.

def get_proximities(park_code: str):
  """
  Given a Park Code, return a dataframe with distance from other parks, sorted by ascending distances.

  Parameter:
    park_code: Park code for specific park.

  Return:
    proximities: Dataframe containing distances (in miles) of parks from selected park, sorted by ascending order, excluding selected park. Shape 61,2 (columns = Park Code and selected park_code) (if select park removed). 
  """
  # Uncomment if park_proximities not loaded globally
  # park_proximities = pd.read_csv('./park_proximities_miles.csv')

  # Ensure park_code is in list of parks, if not return error statement
  if park_code not in list(park_proximities['Park Code']):
          return f"Error: Park code '{park_code}' not found in dataset."

  # Extract column for the given park and sort values by distance in ascending order (closest park first)
  sorted_distances = park_proximities[['Park Code', park_code]].sort_values(by=park_code)

  # Drop first row - should be selected park distance to self = 0
  final_df = sorted_distances.drop(0, axis=0)
  
  return final_df # Returns dataframe of shape 61,2

