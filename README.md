# Upload compromised email accounts/websites to Sumo Logic

The python script:
1. Checks for compromised email accounts from OneLogin and upload result to Sumo Logic
2. Checks for compromised websites and upload result to Sumo Logic

Pre-requisite:
1. OneLogin Access ID with read  only permission.
2. Account in Sumo Logic with access ID and key

Usage: 
1. Fill out Settings.ini
2. (Optional) Get a list of websites to be checked and paste it in sites_to_be_checked.txt file
2. Run `python main.py`
