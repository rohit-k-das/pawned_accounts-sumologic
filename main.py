import requests
import time
import json
import os
import ConfigParser
import mails
import sys
from sumologic import *

# Variables
Config = ConfigParser.ConfigParser()
Config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)),'settings.ini'))

#Get OneLogin credentials 
OneLogin_Client_Id = Config.get('Settings', 'OneLogin_Client_Id')
OneLogin_Secret_Id = Config.get('Settings', 'OneLogin_Secret_Id')

sslverification = True

domains =[
    "everbridge.com", 
    "nixle.com",
    "evb.gg",
    "nixle.us",
    "hipaachat.com",
    "idvsolutions.com"
    ]

#Used for pawned api
def http_get(url):
	response = requests.get(url)
	if response.ok:
		content = json.loads(response.text)
		if content:
			time.sleep(1.3)
			return content
			#return '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()) + content
	if response.status_code == 429:
		sleep_time = int(response.headers['Retry-After'])
		while(sleep_time):
			sys.stdout.write("Pawned API Limit reached. Cooling in %d seconds .......\r" % sleep_time)
			sys.stdout.flush()
			time.sleep(1)
			sleep_time -= 1
		print ''
		time.sleep(0.5)
		http_get(url)
	return ""

#Check breached sites
def breached_domains(s, endpoint, sumo_source_created, sumo_source_link):
    print "CHECKING DOMAINS"
    print "----------------"
    for domain in domains:
    	print "Checking domain %s ...\n" %(domain)
   	url = "https://haveibeenpwned.com/api/v2/breaches" + "?domain=" + domain.lower()
   	results = http_get(url)
   	if results:
   	    breached_site = {}
   	    breached_site["Sites"] = []

	    if not sumo_source_created:
		search_result_breached_site = search_site_sumo_logs(s, domain, endpoint)
		if not search_result_breached_site:
		    search_result_breached_site = []
	    else:
		search_result_breached_site = []
   	    	
	    if results != search_result_breached_site:
	   	for line in results:
	   	    if line not in search_result_breached_site:
	   	    	breached_site["Sites"].append(line)
        
                breached_site["Sites"] = breached_site["Sites"] + search_result_breached_site
	   	
                #Push to Sumologic
	        push_to_sumologic(sumo_source_link,breached_site)

#Check pastes
def get_pastes(email, s, endpoint, push_to_sumo_required, sumo_source_created):
	url = "https://haveibeenpwned.com/api/v2/pasteaccount/" + email
	results = http_get(url)
	pastes = {}
	pastes["Pastes"] = []

	if results:
		if not sumo_source_created:
			_,search_result_paste = search_email_sumo_logs(s, email, endpoint)
                        if not search_result_paste:
			    search_result_paste = []
		else:
			search_result_paste = []
		for paste in results:
			paste.pop("EmailCount")
			paste.pop("Date")
			if paste not in search_result_paste:
			    push_to_sumo_required = True
			    pastes["Pastes"].append(paste)

		#Merge search list and above pastes into one
		pastes["Pastes"] = pastes["Pastes"] + search_result_paste
	return pastes, push_to_sumo_required


#Check breached emails
def breached_emails(email, s, endpoint, push_to_sumo_required, sumo_source_created):
	url = "https://haveibeenpwned.com/api/v2/breachedaccount/" + email + "?includeUnverified=true"
	results = http_get(url)
	breachedaccounts = {}
	breachedaccounts["Email"] = email
	breachedaccounts["Domains"] = []

	if results:
		if not sumo_source_created:
			search_result_domain,_ = search_email_sumo_logs(s, email, endpoint)
                        if not search_result_domain:
			    search_result_domain = []
		else:
			search_result_domain = []
		for site in results:
			temp_dict = {}
			temp_dict["Name"] = site["Name"]
			temp_dict["Domain"] = site["Domain"]
			temp_dict["BreachDate"] = site["BreachDate"]
			temp_dict["ExposedDate"] = site["AddedDate"]
			temp_dict["Verified"] = site["IsVerified"]
			if temp_dict not in search_result_domain:
			    push_to_sumo_required = True
			    breachedaccounts["Domains"].append(temp_dict)
   	
		#Merge breachedaccounts into one
		breachedaccounts["Domains"] = breachedaccounts["Domains"] + search_result_domain
	return breachedaccounts, push_to_sumo_required

def main():
    #Check if settings file has all the items filled
    if not Sumologic_accessid or not Sumologic_accesskey or not collector_name or not source_name or not OneLogin_Client_Id or not OneLogin_Secret_Id:
    	print "ERROR: Fill in the settings.ini file"
    	exit(1)

    #Get Sumologic Collector and Source setup
    s, collector_id, endpoint = sumo_collector()
    sumo_source_link, sumo_source_created = sumo_source(s, collector_id, endpoint)

    #Check Breached sites
    breached_domains(s, endpoint, sumo_source_created, sumo_source_link)  

    #populate Email file
    if mails.email_creation(OneLogin_Client_Id,OneLogin_Secret_Id):
    	with open("Email.txt") as f:
    	    print "CHECKING EMAILS"
    	    print "---------------"
	    for email in f.readlines():
		email = email.strip("\n")
		
		#Check email in SumoLogic
		if email:
		    print "\nChecking email %s...." %(email)			        
		    
                    #Default value of push_to_sumo_required
		    push_to_sumo_required = False

		    #Check pastes and mail in pawned API
	    	    pastes, push_to_sumo_required = get_pastes(email, s, endpoint, push_to_sumo_required, sumo_source_created)
	    	    breachedaccounts, push_to_sumo_required = breached_emails(email, s, endpoint, push_to_sumo_required, sumo_source_created)
	    	    breachedaccounts.update(pastes)
	    	
	    	    #Push to Sumologic
		    if push_to_sumo_required:
		    	#Check if any fields(domain and email) has data
		    	if breachedaccounts["Domains"] != [] or breachedaccounts["Pastes"] != []:
		        	push_to_sumologic(sumo_source_link, breachedaccounts)
				
if __name__ == "__main__":
    main()
