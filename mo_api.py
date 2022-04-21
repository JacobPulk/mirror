import json
import os
import re
import requests
import time
from sys import exit
from both_api import build_request_URL, careful_request

MIN_REQUEST_INTERVAL = 5

USER_AGENT = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"}
APP_API_KEY = "" #private - now having user generate API key themselves

def clean_up_notes(notes):

    notes = re.sub("<\\s*/?\\s*p\\s*>", "", notes)
    notes = re.sub("<\\s*br\\s*/?\\s*>", "\n", notes)
    notes = re.sub("\n\n", "\n", notes)
    notes = "\n"+notes if "\n" in notes else notes
    notes = notes.strip()
    
    return notes

def bad_API_key(parsed):
    
    try:
        bad = re.search("BadApiKey", parsed["errors"][0]["code"], flags=re.IGNORECASE)
        bad = bad or re.search("Bad key", parsed["errors"][0]["details"], flags=re.IGNORECASE)
        
        return bad
    
    except:
        return False
        
def confirm_API_key(api_key, username):

    base_URL = "https://mushroomobserver.org/api2"
    endpoint = "/observations" # is there a better way to confirm the API key?
    params = {"api_key" : api_key, 
                    "user" : username,
                    "format" : "json"}
                    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
            
    return not bad_API_key(parsed)
    
# DEPRECATED - requires my app key, which shouldn't be shared
def get_API_key_with_API(username):
            
    base_URL = "https://mushroomobserver.org/api2"
    endpoint = "/api_keys"
    params = {"api_key" : APP_API_KEY, 
                    "for_user" : username, 
                    "app" : "MO->iNat mirror",
                    "format" : "json"}
    
    parsed = careful_request("POST", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
    
    if bad_API_key(parsed):
        print("MO API key failed. Quitting.\n")
        exit(1)
    
    print("\n1. Make sure you are logged in to MO.\n2. If you have not done this before, check the email address associated with your account - you should have a new email including an \"Activate Key\" link. Click this link. If you have done this before, you can go directly to https://mushroomobserver.org/account/api_keys.\n3. Copy and paste the API Key for \"MO->iNat mirror\" below.")
    
    while True:
    
        inp = input("API key: ")
        
        if confirm_API_key(inp, username):
            print("It worked!")
            return inp
            
        else:
            print("It didn't work. Try again.")
            
def get_API_key(username):

    print("Go to https://mushroomobserver.org/account/api_keys in your browser (select and press enter to copy from here) and log in if necessary. Create a new key for this app (call it something like \"Mushroom Observer/iNaturalist Mirror\"). Copy and paste (with right-click) the API key here.")
    
    while True:

        inp = input("API key: ")
        
        if confirm_API_key(inp, username):
            print("It worked!")
            return inp
            
        else:
            print("It didn't work. Try again.")
            
def get_all_observations(username):

    observations = []
    
    page = 1
    finished = False
    while not finished:

        base_URL = "https://mushroomobserver.org/api2"
        endpoint = "/observations"
        params = {"user" : username, 
                       "page" : str(page), 
                       "detail" : "none", 
                       "format" : "json"}
                       
        parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
    
        try:
            results = [str(r) for r in parsed["results"]]
                
        except:
            print("Response did not include results. Quitting.\n")
            exit(1)
            
        else:
            if len(results) > 0:
                observations += results
            else:
                finished = True
                break
                
        page += 1
        
    return observations
    
def get_full_obses(username, page, api_key):

    base_URL = "https://mushroomobserver.org/api2"
    endpoint = "/observations"
    params = {"user" : username, 
                   "page" : str(page), 
                   "detail" : "high", 
                   "format" : "json", 
                   "api_key" : api_key}
                   
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
    
    try:
        full_obses = parsed["results"]
        
    except:
        print("Response did not include observations. Dumping and quitting.\n")
        with open("JSON_dump.json", "wb") as outf:
            outf.write(parsed)
        exit(1)
        
    else:        
        return full_obses
               
def get_images(urls):

    images = []
    
    for url in urls:

        content = careful_request("GET", url, headers = USER_AGENT, demand_json = False)
        
        if len(content) < 5000:
            print("Warning: got file possibly too small to be an image ("+str(len(content))+" bytes).")
            
        images.append(content)
        
    return images
    
def add_link(username, MOID, iNatID, current_date, MO_API_key):

    ### get original notes ###
            
    base_URL = "https://mushroomobserver.org/api2"
    endpoint = "/observations"
    params = {"id" : MOID, 
                   "detail" : "high", 
                   "format" : "json"}
    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
    
    try:
        obs = parsed["results"][0]
    except:
        print("Didn't get observation data from MO. Quitting.\n")
        exit(1)
    else:
        original_notes = obs["notes"] if "notes" in obs else ""
        original_notes = clean_up_notes(original_notes)


    ### construct new notes ###
    addendum = "Mirrored on iNaturalist as <a href=\"https://www.inaturalist.org/observations/"+iNatID+"\">observation "+iNatID+"</a> on "+current_date+"."
    if original_notes == "":
        new_notes = addendum
    else:
        new_notes = original_notes + "\n\n&#8212;\n\n" + addendum
    
    
    ### patch new notes ###
            
    base_URL = "https://mushroomobserver.org/api2"
    endpoint = "/observations"
    params = {"user" : username, 
                   "api_key" : MO_API_key, 
                   "id" : MOID, 
                   "set_notes" : new_notes, 
                   "log" : "no", 
                   "format" : "json"}
    
    parsed = careful_request("PATCH", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
    
    if bad_API_key(parsed):
        print("MO API key failed. Quitting.\n")
        exit(1)
        
def view_particular(MOID):

    base_URL = "https://mushroomobserver.org/api2"
    endpoint = "/observations"
    params = {"id" : MOID, 
                    "detail" : "high", 
                    "format" : "json"}
                    
    parsed = careful_request("GET", build_request_URL(base_URL, endpoint, params), headers = USER_AGENT)
    
    print(json.dumps(parsed, indent = 4, sort_keys = False))