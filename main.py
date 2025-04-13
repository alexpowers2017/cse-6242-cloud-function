from flask import jsonify
from utils import recommend_parks

# This is a header that needs to be in all responses going to a browser or else it breaks
base_header = {'Access-Control-Allow-Origin': '*'}

def handle_preflight_request():
    """ Gives the necessary response to a confirmation request that the browser will send before the actual response. """
    headers = base_header.copy()
    headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return ('', 204, headers)


def handle_post_request(request):  

    # Check to make sure all the keys are correct or return a failed response
    missing_keys = [] 
    for expected_key in ['prompt', 'month', 'crowdPreference']:
        if expected_key not in request.json.keys():
            missing_keys.append(expected_key)
    if missing_keys:
        message = {'message': f'Missing the following keys: {",".join(missing_keys)}'}
        return (jsonify(message), 404, base_header)

    # Pull out the request elements into variables
    prompt = request.json['prompt']
    month = request.json['month']
    crowd_preference = request.json['crowdPreference']
    city = request.json['city'] # Added by Ian

    park_recommendations = recommend_parks(prompt, month, crowd_preference, city, 10)

    message = {
        'message': 'success',
        'data': park_recommendations
    } 
    return (jsonify(message), 200, base_header)


def main(request):
  
    if request.method == 'OPTIONS':
        return handle_preflight_request()

    elif request.method == 'GET':
        return (jsonify({'message': 'success'}), 200, base_header)

    elif request.method == 'POST':
        return handle_post_request(request)

    else:
        headers = {'Access-Control-Allow-Origin': '*'}
        message = {'message': 'unsupported method'}
        return (jsonify(message), 404, headers)
