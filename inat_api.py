import base64
import hashlib
import json
import random
import re
import socket
from string import ascii_uppercase, ascii_lowercase, digits
import time
from sys import exit
from both_api import build_request_URL, request_pause, careful_request


USER_AGENT = {"User-Agent" : "Mushroom Observer/iNaturalist Mirror"}

APP_ID = "2c5FnA4ASUw8d-3b2vSF5kRFyNcI3smfhiPvyxvFghA"
APP_SECRET = "" # private - now using PKCE, not ROPC

#INAT_REALIZE_JWT = 0 # seconds to wait for iNat to recognize JWT it created - not sure if > 0; would explain a bug


### PKCE variables ###

VERIFIER_CHARACTERS = list(ascii_uppercase+ascii_lowercase+digits)+["-",".","_","~"]
REDIRECT_URI = "http://127.0.0.1:65432"
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 65432
BROWSER_REQUEST_TIMEOUT = 2

### end PKCE variables ###

if REDIRECT_URI != "http://"+LOCAL_HOST+":"+str(LOCAL_PORT):
    print("iNat application callback URL ("+REDIRECT_URI+") does not match local host/port ("+LOCAL_HOST+", "+str(LOCAL_PORT)+").")
    exit(1)

def build_headers(access_token = None):
    
    if access_token:
        return USER_AGENT | {"Authorization" : access_token}
    else:
        return USER_AGENT

# def pause_for_JWT(timestamp = 0)

    # age = time.time()-timestamp
    # time_till_recognized = max(INAT_REALIZE_JWT-age,0)
    # if time_till_recognized > 0:
        # time.sleep(time_till_recognized)
     
def confirm_JWT(jwt, username, timestamp = 0):

    #pause_for_JWT(timestamp)

    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/users/me"
    params = {}
    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params), headers = build_headers(jwt))
    
    try:
        response_username = parsed["results"][0]["login"]
    except:
        return False
    else:
        return response_username.lower() == username.lower()

def get_param_from_socket(field):


    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

        s.bind((LOCAL_HOST, LOCAL_PORT))
        s.listen()
        
        conn, addr = s.accept()
            
        if addr[0] != LOCAL_HOST:
            print("\nReceived unexpected connection besides "+LOCAL_HOST+". Quitting.\n")
            exit(1)
        
        with conn:
        
            print("\nReceived connection from browser. Waiting for you to enter the URL above...")
            
            timer_start = time.time()
            timed_out = False
            while not timed_out:
            
                if time.time() >= timer_start + BROWSER_REQUEST_TIMEOUT:
                    timed_out = True
                    break
                    
                data = conn.recv(1024)
                
                if not data:
                    timed_out = False
                    break
                    
                request_line = next(filter(lambda x : x.split(" ")[0] == "GET", data.decode("ascii").split("\n")), None)
                
                if request_line:
                
                    splat = request_line.split(" ")[1].split("?")
                    
                    # expect another request for (favicon.ico) without param part from previous attempt. Listen for more
                    if len(splat) < 2:
                        continue
                        
                    endpoint = splat[0]
                    param_part = splat[1]
                    
                    try:
                        param_pairs = [p.split("=") for p in param_part.split("&")]
                    except:
                        print(f"Couldn't interpret parameters in URL in the following line: \"{request_line}\". Quitting.\n")
                        conn.send(("HTTP/1.1 200 OK\n"+"Content-Type: text/html\n\n"+"MO->iNat Mirror couldn't get the authorization code. :(").encode("ascii"))
                        exit(1)
                        
                    else:
                    
                        param_dictionary = dict(param_pairs)
                        
                        if field in param_dictionary:
                            print("Got authorization code (via your browser) from iNat.")                            
                            conn.send(("HTTP/1.1 200 OK\n"+"Content-Type: text/html\n\n"+"MO->iNat Mirror got the authorization code. Thank you!").encode("ascii"))
                            return param_dictionary[field]
                            
                        else:
                            print("Couldn't find code in params. Quitting.\n")
                            conn.send(("HTTP/1.1 200 OK\n"+"Content-Type: text/html\n\n"+"MO->iNat Mirror couldn't get the authorization code. :(").encode("ascii"))
                            exit(1)
                            
                else:
                    print("Couldn't find request URL in data from browser. Quitting.\n")
                    conn.send(("HTTP/1.1 200 OK\n"+"Content-Type: text/html\n\n"+"MO->iNat Mirror couldn't get the authorization code. :(").encode("ascii"))
                    exit(1)
                        
def get_JWT_ROPC(username, password):
            
            
    ###### get access token w/ user AND client credentials ######

    iNat_pause()

    base_URL = "https://www.inaturalist.org"
    endpoint = "/oauth/token"
    data_payload = {"client_id" : APP_ID, 
                            "client_secret" : APP_SECRET, 
                            "grant_type" : "password", 
                            "username" : username, 
                            "password" : password}
                            
    parsed = careful_request("POST", build_request_URL(base_URL, endpoint), data = data_payload, headers = build_headers())
    
    try:
        access_token = parsed["access_token"]
    except:
        print("Did not get access token. Try again.")
        return None
    else:
        print("Got access token.")
            
            
    ###### exchange access token for JWT ######
    
    base_URL = "https://www.inaturalist.org"
    endpoint = "/users/api_token"
    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint), headers = build_headers() | {"Authorization" : "Bearer "+access_token}) # needs "Bearer " - different from what's done in build_headers
    
    try:
        jwt = parsed["api_token"]
    except:
        print("Didn't get JWT from iNaturalist. Try again.")
        return None
    else:
        return jwt

def get_JWT_PKCE():

    ###### generate verifier/challenge pair ######

    code_verifier = "".join([random.choice(VERIFIER_CHARACTERS) for i in range(128)])
    #code_verifier = "pIUgx4tiqFpaOUz0HMc_QbIyQlL901w8mRmkrmhEJ_E" #corresponding challenge should be "_drLS7o5FwkfUiBhlq2hwJnK_SC6yE7sKOde5O1fdzk"
    #print("CV is "+code_verifier)
    cv_hashed = hashlib.sha256(code_verifier.encode("UTF-8")).digest()
    #print("CV hashed is "+cv_hashed)
    cv_encoded = base64.b64encode(cv_hashed).decode()
    #print("CV base64 encoded is "+cv_encoded)
    cv_detrailed = cv_encoded.split("=")[0]
    #print("CV detrailed is "+cv_detrailed)
    code_challenge = cv_detrailed.replace("+","-").replace("/","_")
    #print("CC is "+code_challenge)
    


    ###### get authorization code from logged-in iNat ######

    base_URL = "https://www.inaturalist.org"
    endpoint = "/oauth/authorize"
    params = {"client_id" : APP_ID, 
                    "redirect_uri" : REDIRECT_URI, 
                    "response_type" : "code", 
                    "code_challenge_method" : "S256",
                    "code_challenge" : code_challenge}
                    
    full_URL = build_request_URL(base_URL, endpoint, params)
    
    request_pause("iNat", 0)
    print("\nMake sure you are logged in to your target iNat account (or not logged in to any). Select the entire following URL and press enter (NOT ctrl+c) to copy it, then navigate to it in your browser. Log into iNat if prompted there; either way return here.\n")
    print(full_URL)
    
    code = get_param_from_socket("code")
    
    
    
    ###### exchange authorization code for access token ######

    base_URL = "https://www.inaturalist.org"
    endpoint = "/oauth/token"
    params = {"client_id" : APP_ID, 
                    "code" : code, 
                    "redirect_uri" : REDIRECT_URI, 
                    "grant_type" : "authorization_code", 
                    "code_verifier" : code_verifier}
                    
    parsed = careful_request("POST", build_request_URL(base_URL, endpoint, params))
    
    try:
        access_token = parsed["access_token"]
    except:
        print("Did not get access token. Try again.")
        return get_JWT_PKCE()
    else:
        print("Got access token.")
        
            
            
    ###### exchange access token for JWT ######
    
    base_URL = "https://www.inaturalist.org"
    endpoint = "/users/api_token"
    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint), headers = build_headers() | {"Authorization" : "Bearer "+access_token}) # needs "Bearer " - different from what's done in build_headers
    
    try:
        JWT = parsed["api_token"]
    except:
        print("Did not get JWT. Try again.")
        return get_JWT_PKCE()
    else:
        print("Got JWT.")
        return JWT

def get_mirrored_MOIDs(username):


    params = {"user_login" : username, "per_page" : "200"}
    
    mirroreds = []
    page = 1

    while True:
        
    
        base_URL = "https://api.inaturalist.org/v1"
        endpoint = "/observations"
        
        parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params | {"page" : page}), headers = build_headers())
        
        
        if "results" in parsed:
            results_list = parsed["results"]
            
            # ran out of results (presumably)
            if len(results_list) == 0:
                break
            
        # ran out of results (presumably)
        else:
            break
    
        for result in results_list:
            if "ofvs" in result:
                for ofv in result["ofvs"]:
                    if ofv["field_id"] == 5005: ## Mushroom Observer URL
                        m_ID = re.match(".*/(\\d{1,6})(\\?|$)", ofv["value"])
                        if m_ID:
                            mirroreds.append(m_ID.group(1))
                            continue
            
        page += 1
        
    return set(mirroreds)

def search_for_name(name):

    parsed = careful_request("GET", build_request_URL("https://api.inaturalist.org", "/v1/taxa", {"q" : name}), headers = build_headers())
    
    search_results = parsed["results"] if "results" in parsed else []
    
    return search_results
 
def create_obs(obj, jwt):


    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/observations"
    
    parsed = careful_request("POST", build_request_URL(base_URL, endpoint), data = obj, headers = build_headers(jwt))
        
    try:
        iNatID = str(parsed["id"])
        
    except:
        print("Got result without obs ID. Dumping and quitting.\n")
        with open("JSON_dump.json", "w", encoding="utf8") as outf:
            outf.write(json.dumps(parsed, indent = 4, sort_keys = False))
        exit(1)
        
    else:
        return iNatID
        
def post_fields(iNatID, fields, jwt):

    for field_ID in fields:
    
        field_value = fields[field_ID]
        
        base_URL = "https://api.inaturalist.org/v1"
        endpoint = "/observation_field_values"
        params = {"observation_id" : int(iNatID), 
                        "observation_field_id" : int(field_ID), 
                        "value" : field_value}
        obj = json.dumps({"observation_field_value" : params})
        
        parsed = careful_request("POST", build_request_URL(base_URL, endpoint), data = obj, headers = build_headers(jwt))
 
def get_existing_proposal(iNatID):

    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/observations/"+iNatID
    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint), headers = build_headers())
    
    try:
        identifications = parsed["results"][0]["identifications"]
    
    except:    
        print("Couldn't find expected name proposal. Quitting.\n")
        exit(1)
    
    else:
        if len(identifications) > 1:
            print("Warning: Unexpectedly found multiple identifications already on iNat observation.")
            
        identification = identifications[0]
            
        identification_ID = str(identification["id"])
        taxon_ID = str(identification["taxon_id"])
        iNat_name = str(identification["taxon"]["name"])
        iNat_rank = str(identification["taxon"]["rank"])
        
        return identification_ID, taxon_ID, iNat_name, iNat_rank
    
def update_proposal(identification_ID, obj, jwt):

    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/identifications/"+identification_ID
    
    parsed = careful_request("PUT", build_request_URL(base_URL, endpoint), data = obj, headers = build_headers(jwt))

def post_image(iNatID, image, jwt):

    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/observation_photos"
    params = {"observation_photo[observation_id]" : int(iNatID)}
    images = {"file" : image}
                           
    parsed = careful_request("POST", build_request_URL(base_URL, endpoint, params), files = images, headers = build_headers(jwt))

def update_obs(iNatID, obj, jwt):

    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/observations/"+iNatID
    
    parsed = careful_request("PUT", build_request_URL(base_URL, endpoint), data = obj, headers = build_headers(jwt))
    
def delete_observation(iNatID, jwt):

    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/observations/"+iNatID
    
    parsed = careful_request("DELETE", build_request_URL(base_URL, endpoint), headers = build_headers(jwt))
    
def view_particular(iNatID):
    
    base_URL = "https://api.inaturalist.org/v1"
    endpoint = "/observations/"+iNatID
    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint), headers = build_headers())
    
    print(json.dumps(parsed, indent = 4, sort_keys = False))