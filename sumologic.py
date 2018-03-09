import common
import ConfigParser
import os
import requests
import urllib
import time
import json
import datetime

# Variables
Config = ConfigParser.ConfigParser()
Config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)),'settings.ini'))

# The default Sumologic Credentials to be used
Sumologic_accessid = Config.get('Settings', 'Sumologic_accessid')
Sumologic_accesskey = Config.get('Settings', 'Sumologic_accesskey')

#Default Sumologic Collector name to be used
collector_name = Config.get('Settings', 'Sumologic_Hosted_Collector_Name')

#Default Source Name for Sumologic Collector
source_name = Config.get('Settings', 'Sumologic_Hosted_Source_Name')

#Hosted_Collector_JSON
Hosted_Collector = {
	"collector":{
		"collectorType":"Hosted",
		"name":collector_name ,
		"description":"Breached Account Collector",
		"category":""
	}
}

#Hosted_Source_JSON
Hosted_Source = {
	"api.version":"v1",
	"source":{
		"category":"security/pwned",
		"multilineProcessingEnabled":True,
		"useAutolineMatching":True,
		"forceTimeZone":False,
		"sourceType":"HTTP",
		"name":source_name,
		"messagePerRequest":True,
		"automaticDateParsing":False
	}
}

#Setup authenticated session
def sumo_authentication():
	s = requests.Session()
	s.auth = (Sumologic_accessid, Sumologic_accesskey)
	s.headers = {"Content-Type": "application/json", "accept": "application/json"}
	return s

def default_endpoint(s):
	#Get endpoint based on location
	endpoint = "https://api.sumologic.com/api/v1/collectors"
	resp = s.get(endpoint)  # Dummy call to get endpoint
	endpoint = resp.url.replace('/collectors', '')  # dirty hack to sanitise URI and retain domain
        return endpoint
    
        if resp.status_code == 429:
	    time.sleep(3)
	    default_endpoint(s)
	else:
	    print "ERROR: Unable to find default endpoint. Status code %d." %(resp.status_code)

def search_collector(s, endpoint):
	#Default collector id value
	collector_id = ""

	url = endpoint + '/collectors'
	resp = s.get(url)
	if resp.ok:
	    for collector in resp.json()["collectors"]:
		if collector_name in collector["name"]:
		    collector_id = collector["id"]
		    print "Found collector " + collector_name + " with id " + str(collector_id) + ".\n"
		    break
	    return str(collector_id)
	elif resp.status_code == 429:
	    time.sleep(3)
	    search_collector(s, endpoint)
	else:
	    print "ERROR: Unable to find search for collector. Status code %d. \nReason: %s" %(resp.status_code, resp.json()["message"])
    	exit(1)

def setup_sumo_collector(s, endpoint):
	url = endpoint + '/collectors'
	resp = s.post(url, json=Hosted_Collector)
	if resp.ok:
	    collector_id = str(resp.json()["collector"]["id"])
	    print "Collector with "+ str(collector_id) + " setup in SumoLogic.\n"
	    return collector_id
	elif resp.status_code == 429:
	    time.sleep(3)
	    setup_sumo_collector(s, endpoint)
	else:
	    print "ERROR: Error setting up collector due to %s." %(resp.json()["message"])
	    exit(1)

#SumoLogic Collector
def sumo_collector():
	s = sumo_authentication()

	#Get endpoint based on location
	endpoint = default_endpoint(s)

	#Check if collector already exists from collector name and type
	collector_id = search_collector(s, endpoint)

	#if collector is not present
	if collector_id == "":
	    collector_id = setup_sumo_collector(s, endpoint)

	return s, collector_id, endpoint

#Check if Source exists collector
def search_source(s, endpoint, collector_id):
	#Default source id and sumo_source_created
	sumo_source_link = ""
	
	url = endpoint + "/collectors/" + collector_id + "/sources"
	resp = s.get(url)
	if resp.ok:
	    #Check if only one source is present
	    if len(resp.json()) == 1:
		for source in resp.json()["sources"]:
		    if source_name in source["name"]:
			sumo_source_link = source["url"]
			print "Found source " + source_name + " for collector " + collector_id + ".\n"
			break
		return sumo_source_link
	    else:
		print "ERROR: Multiple sources found."
		exit(1)
	elif resp.status_code == 429:
	    time.sleep(3)
	    search_source(s, endpoint, collector_id)
	else:
	    print "ERROR: Unable to find search for source. Status code %d. \nReason: %s" %(resp.status_code, resp.json()["message"])
    	    exit(1)

def setup_sumo_source(s, endpoint, collector_id):
	url = endpoint + "/collectors/" + collector_id + "/sources"
	resp = s.post(url, json=Hosted_Source)
	if resp.ok:
	    sumo_source_link = resp.json()["source"]["url"]
	    print "HTTP Source for "+ collector_id + " setup in SumoLogic.\n"
	    sumo_source_created = True
	    return sumo_source_created, sumo_source_link
	elif resp.status_code == 429:
	    time.sleep(3)
	    setup_sumo_source(s, endpoint, collector_id)
	else:
	    print "ERROR: Error setting up HTTP source for " + collector_id +" due to " + resp.json()["message"] + "\n"
	    exit(1)
	
#HTTP Source for hosted Collector
def sumo_source(s, collector_id, endpoint):
	sumo_source_created = False

	#Check if Source exists collector
	sumo_source_link = search_source(s, endpoint, collector_id)

	#If Source not in Collector, create source
	if sumo_source_link == "":
	    sumo_source_created, sumo_source_link = setup_sumo_source(s, endpoint, collector_id)

	return sumo_source_link, sumo_source_created

#Push to source
def push_to_sumologic(url, data):
	data = json.dumps(data)
	resp = requests.post(url, data=data)
	if resp.ok:
	    print "Data pushed to collector."

#Get number of logs from search job id
def number_of_logs(s, endpoint, job_id):
	url = endpoint + '/search/jobs/' + job_id
	while True:
	    resp = s.get(url)
	    if resp.ok:
		if resp.json()["state"] == "DONE GATHERING RESULTS":
                    break
                time.sleep(1)
	    elif resp.status_code == 429:
		time.sleep(3)
                number_of_logs(s, endpoint, job_id)
	    else:
		print "ERROR: Error while searching job id %s. Status code %d. Reason: %s" %(job_id, resp.status_code,resp.json()["message"])
		break
        message_count = resp.json()["messageCount"]
	if message_count:
	    return message_count
	else:
	    return 0
		
# Get recent log from search
def latest_log_from_search(s, endpoint, job_id):
	message_url = endpoint + '/search/jobs/' + job_id + '/messages?offset=0&limit=1'
	resp = s.get(message_url)
	if resp.ok:
	    return resp.json()["messages"][0]
	elif resp.status_code == "429":
	    time.sleep(3)
	    latest_log_from_search(s, endpoint, job_id)
        else:
            print "ERROR: Unable to get logs from job id %s." %(job_id)

# Delete search job
def delete_search(s, endpoint, job_id):
	job_id_url = endpoint + '/search/jobs/' + job_id
	resp = s.delete(job_id_url)
        if resp.ok:
            return
	elif resp.status_code == "429":
	    time.sleep(3)
	    delete_search(s, endpoint, job_id)
        else:
	    print "ERROR: Unable to delete search job " + job_id + " due to " + resp.json()["message"] 

#Get breach results of email account from sumologic
def search_email_sumo_logs(s, email, endpoint):
	search_url = endpoint + '/search/jobs'
	query = '_sourceCategory=security/pwned and ' + email + '|json \"Domains\",\"Email\",\"Pastes\"'
	s.headers = {"Content-Type": "application/json", "accept": "application/json"}	
	current_time = str(datetime.datetime.now()).replace(" ","T").split(".")[0]
	parameters = {
			"query":query,
			"from":"2017-11-28T13:01:02", #Hard coded to a value that works
			"to":current_time,
			"timeZone":"PST"
		    }
	resp = s.post(search_url, json=parameters)
	if resp.ok:
	    job_id = resp.json()["id"]
	    if job_id:
		if number_of_logs(s, endpoint, job_id) != 0:
		    log = latest_log_from_search(s, endpoint, job_id)
		    delete_search(s, endpoint, job_id)
                    domains = log["map"]["domains"]
		    pastes = log["map"]["pastes"]
		    return json.loads(domains),json.loads(pastes)
		else:
		    domains = []
		    pastes = []
		    return domains, pastes
	elif resp.status_code == "429":
	    time.sleep(3)
	    search_email_sumo_logs(s, email, endpoint)
	else:
	    print "ERROR: Error while searching email %s. Status code %d." %(email, resp.status_code)
	    domains = []
	    pastes = []
	    return domains, pastes

#Get breach results of site from sumologic
def search_site_sumo_logs(s, site, endpoint):
	search_url = endpoint + '/search/jobs'
	query = '_sourceCategory=security/pwned and ' + site + '|json \"Sites\"'
	s.headers = {"Content-Type": "application/json", "accept": "application/json"}	
	current_time = str(datetime.datetime.now()).replace(" ","T").split(".")[0]
	parameters = {
			"query":query,
			"from":"2017-11-28T13:01:02", #Hard coded to a value that works
			"to":current_time,
			"timeZone":"PST"
		    }
	resp = s.post(search_url, json=parameters)
	if resp.ok:
	    job_id = resp.json()["id"]
	    if job_id:
		if number_of_logs(s, endpoint, job_id) != 0:
		    log = latest_log_from_search(s, endpoint, job_id)
		    delete_search(s, endpoint, job_id)
                    sites = log["map"]["sites"]
                    return json.loads(sites)
                else:
                    sites = []
                    return sites
	elif resp.status_code == "429":
	    time.sleep(3)
	    search_site_sumo_logs(s, site, endpoint)
	else:
	    print "ERROR: Error while searching site %s. Status code %d. \nReason: %s" %(site, resp.status_code, resp.json()["message"])	
            sites = []
	    return sites
