#!/usr/bin/env python3

import requests

def send(method, url, headers, json):
  try:
    if( method == "POST" ):
      response = requests.post(url, headers=headers, json=data, verify=False, auth=requests.auth.HTTPBasicAuth( "ctlabs", "secret123!" ) )
      response.raise_for_status()
    elif( method == "PUT"):
      response = requests.put(url, headers=headers, json=data, verify=False, auth=requests.auth.HTTPBasicAuth( "ctlabs", "secret123!" ) )
      response.raise_for_status()
  except requests.exceptions.RequestException as e:
    print(f"An error occured: {e}")


host     = "192.168.30.32:3000"
headers  = { "accept" : "application/json", "Content-Type" : "application/json" }
reponame = "labs"

url     = f"https://{host}/api/v1/user/repos"
data    = {
        "auto_init"          : True,
        "default_branch"     : "main",
        "description"        : "created via curl",
        "gitignores"         : "",
        "issue_labels"       : "Advanced",
        "license"            : "MIT",
        "name"               : f"{ reponame }",
        "object_format_name" : "sha1",
        "private"            : True,
        "readme"             : "",
        "template"           : False,
        "trust_model"        : "default"
}

send("POST", url, headers, data)

# ---

url     = f"https://{ host }/api/v1/repos/ctlabs/{ reponame }/collaborators/atlantis"
data    = { "permissions" : f"{ reponame }:write" }

send("PUT", url, headers, data)

# ---


url     = f"https://{ host }/api/v1/repos/ctlabs/{ reponame }/hooks"
data    = {
  "active"               : True,
  "type"                 : "gitea",
  "authorization_header" : str(requests.auth.HTTPBasicAuth( "ctlabs", "secret123!" )),
  "branch_filter"        : "string",
  "config": {
      "content_type": "json",
      "url": "https://ats1.ctlabs.internal:4141/events"
    },
  "created_at": "2025-01-12T05:49:28.786Z",
  "events": [
    "push",
    "issue_comment",
    "pull_request",
    "pull_request_comment",
    "pull_request_review_approved",
    "pull_request_review_rejected",
    "pull_request_review_comment",
    "pull_request_sync"
  ],
  "id": 0,
  "updated_at": "2025-01-12T05:49:28.786Z"
}

send("POST", url, headers, data)