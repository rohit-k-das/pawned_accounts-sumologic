import requests
import os
import common


def create_onelogin_token(authorized):
	url = "https://api.us.onelogin.com/auth/oauth2/v2/token"
	header = {
		"Authorization":authorized,
		"Content-Type":"application/json"
	}
	data = {"grant_type":"client_credentials"}
	response = requests.post(url, headers=header, json= data)
	if response.ok:
		access_token = response.json()["access_token"]
		refresh_token = response.json()["refresh_token"]
		created_at = response.json()["refresh_token"]
		print "Onelogin token created successfully.\n"
		return access_token
	else:
		print "OneLogin token creation failed due to %s.\n" %(response.json()["status"]["message"])
		return ""

def revoke_onelogin_token(onelogin_token,authorized):
	url = "https://api.us.onelogin.com/auth/oauth2/revoke"
	header = {
		"Authorization":authorized,
		"Content-Type":"application/json"
	}
	
	data = {"access_token":onelogin_token}
	response = requests.post(url, headers= header, json= data)
	if response.ok:
		if response.json()["status"]["message"] == "Success":
			print "OneLogin token revoke successful.\n"
	else:
		print response.json()
		print "OneLogin token revoke failed due to %s.\n" %(response.json()["status"]["message"])

def mail_id(onelogin_token,fobj,file_previously_present):
    #Load all emails to a list
    if file_previously_present:
	email_list = fobj.read().split()
    else:
        email_list = []

    url = "https://api.us.onelogin.com/api/1/users?sort=+id"
    header = {"Authorization":"bearer:" + onelogin_token}
    response = requests.get(url, headers= header)
    while(True):
    	if response.ok:
    		for profile in response.json()["data"]:
        		if profile["email"] and profile["email"] not in email_list:
        			fobj.write(profile["email"] + "\n")
        	if response.json()["pagination"]["next_link"]:
        		url = response.json()["pagination"]["next_link"]
        		response = requests.get(url, headers= header)
        	else:
        	   break
    print "Email extracted from OneLogin successfully.\n"
    
def email_creation(client_id,client_secret):
	print "GATHERING EMAIL FROM ONELOGIN"
	print "-----------------------------"
	authorized = "client_id: %s, client_secret: %s" %(client_id,client_secret)
	onelogin_token = create_onelogin_token(authorized)
	if onelogin_token:
		if not common.is_non_zero_file("Email.txt"):
			with open("Email.txt",'w+') as fobj:
				mail_id(onelogin_token,fobj,file_previously_present=False)
		elif common.is_non_zero_file("Email.txt"):
			with open("Email.txt",'r+') as fobj:
				mail_id(onelogin_token,fobj,file_previously_present=True)
		revoke_onelogin_token(onelogin_token,authorized)
		return True

	else:
		return False
