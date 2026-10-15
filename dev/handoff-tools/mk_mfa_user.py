import json, sys, requests, pyotp, urllib3

urllib3.disable_warnings()
B = "https://localhost:8443"
SP = sys.argv[1]
admin_tok = open(f"{SP}/token").read().strip()
H = {"Authorization": f"Bearer {admin_tok}"}
r = None

r = requests.post(
    f"{B}/api/v2/auth/login/",
    verify=False,
    json={"username": "tester", "password": "TesterPass123"},
)
print("login", r.status_code, r.text[:200])
tok = r.json()["data"]["token"]
H2 = {"Authorization": f"Bearer {tok}"}
r = requests.post(f"{B}/api/v2/users/3/totp/", headers=H2, verify=False)
print("totp create", r.status_code, r.text[:300])
otp = r.json()["data"]["otp"]
secret = otp.get("secret") or otp.get("totp_secret")
tid = otp.get("id")
code = pyotp.TOTP(secret).now()
r = requests.post(
    f"{B}/api/v2/users/@me/totp/{tid}/verify/",
    headers=H2,
    verify=False,
    json={"name": "Phone", "totp": int(code)},
)
print("verify", r.status_code, r.text[:400])
json.dump(
    {"secret": secret, "backup": r.json()["data"]["backup_codes"]},
    open(f"{SP}/mfa.json", "w"),
)
