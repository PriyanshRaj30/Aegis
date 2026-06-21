from app.services.token_bucket import check_token_bucket
# First call — bucket is full
print(check_token_bucket("test-ip"))  
print(check_token_bucket("test-ip"))   
print(check_token_bucket("test-ip")) 
print(check_token_bucket("test-ip"))
print(check_token_bucket("test-ip"))  
print(check_token_bucket("test-ip"))  
