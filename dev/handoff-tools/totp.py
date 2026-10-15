import json, sys, pyotp

print(pyotp.TOTP(json.load(open(sys.argv[1]))["secret"]).now())
