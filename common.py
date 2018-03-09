import os

def is_non_zero_file(fpath):  
    try:
    	file = os.path.isfile(fpath) and os.path.getsize(fpath) > 0
    	if file:
    		return True
    	else:
    		return False
    except Exception as e:
    	print e.message

