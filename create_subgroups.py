import sys
if sys.version_info[0] < 3:
    raise RuntimeError("This needs to be run with Python 3")

import json
import os
from pprint import pprint
import requests

# Set these env variables to avoid having to type in your login info, e.g.
# > export GROUPSIO_EMAIL=test@example.com
EMAIL_ENV_VAR = "GROUPSIO_EMAIL"
PASSWORD_ENV_VAR = "GROUPSIO_PASSWORD"

TOP_LEVEL_GROUP_NAME = "swansway"
SKIP_CONFIGURE_SUBGROUPS = {"groupprocess"}

## General request helpers

class GroupsIoRequestError(RuntimeError):
    def __init__(self, route, resp):
        super().__init__("{} error: {}\n{}".format(route, resp, resp.content))
        self.code = resp.status_code
        # Only populated for 400s
        # Docs: https://groups.io/api#errors
        self.type = resp.json().get("type")
        self.extra = resp.json().get("extra")

def validate_response(route, resp):
    if resp.status_code != 200:
        raise GroupsIoRequestError(route, resp)

def get_route(path_suffix):
    return "https://groups.io/api/v1/{}".format(path_suffix)

def post(path_suffix, cookies, data):
    route = get_route(path_suffix)
    resp = requests.post(route, data=data, cookies=cookies)
    validate_response(route, resp)
    return resp

def get(path_suffix, cookies, params):
    route = get_route(path_suffix)
    resp = requests.get(route, params=params, cookies=cookies)
    validate_response(route, resp)
    return resp

def pretty_print(resp):
    pprint(json.loads(resp.content))

def get_input(prompt):
    return input("{}: ".format(prompt)).lower()

def yes_no_input(prompt):
    return get_input("{} (y/n)".format(prompt)) == "y"

## Subgroup-specific helpers

def add_subgroup(name, desc, cookies, csrf_token):
    print("Creating subgroup...")
    # Docs: https://groups.io/api#create_sub_group
    post("createsubgroup", cookies, {
        "group_name": TOP_LEVEL_GROUP_NAME,
        "sub_group_name": name,
        "desc": desc,
        "csrf": csrf_token,
        # Privacy -> Visibility
        # Visible to members of parent group, but not general public
        # This is the only interesting setting you can set during creation; need to do a
        # separate update call for more customization
        "privacy": "sub_group_privacy_limited_archives",
    })

def configure_subgroup(name, title, desc, cookies, csrf_token):
    print("Configuring {} subgroup...".format(name))
    if name in SKIP_CONFIGURE_SUBGROUPS:
        print("Skipping group {}, it has custom settings".format(name))
        return
    parent_scoped_name = "{}+{}".format(TOP_LEVEL_GROUP_NAME, name)

    # Docs: https://groups.io/api#update_group
    # This only updates things that don't already default to the value we want.
    post("updategroup", cookies, {
        "group_name": parent_scoped_name,
        "csrf": csrf_token,

        "title": title,
        "desc": desc,

        # Privacy -> Visibility
        # This was probably already set during creation, but just in case:
        "privacy": "sub_group_privacy_limited_archives",
        # Main group members should be able to see the members even if they aren't in the subgroup
        "members_visible": "group_view_members_subs",

        # Spam Control -> Restricted Membership
        # Do members require approval before being allowed to join the group?
        # I don't think we need this, since the sub-group is only visible to parent group members so
        # non-residents can't even attempt to join, and we want residents to be able to join at will
        "restricted": "false",

        # Message Policies
        # Non-residents can post, but their posts will be moderated
        "allow_non_subs_to_post": "true",
        # All Swan's residents can post (unmoderated), even if they aren't in this subgroup
        "allow_parent_subs_to_post": "true",
        # Default to reply to sender (rather than reply-all)
        "reply_to": "group_reply_to_sender",

        # Features
        # I'm still kinda unclear on the difference between member directory and member list, but
        # I think this makes the directory viewable to members
        "member_directory_access": "group_access_limited",
        # Disable a bunch of extra crap we don't need (makes UI less cluttered)
        # Things that could be disabled, but aren't: member_directory, polls, photos
        "calendar_access": "group_access_none",
        "files_access": "group_access_none",
        "database_access": "group_access_none",
        "wiki_access": "group_access_none",
        "chat_access": "group_access_none",
        # Auto-resize photos sent in emails if larger than 2048x2048
        "max_photo_size_email": "max_photo_size_medium"
    })

    # By default, newly created groups get this "member notice" that sends a welcome email to anyone we add
    # to the group - this is spammy and redundant with another email that also gets auto-sent to them
    # Docs: https://groups.io/api#get_member_notices
    notices_resp = get("getmembernotices", cookies, {
        "group_name": parent_scoped_name,
        "type": "member_notice_joining"
    })
    # Docs: https://groups.io/api#delete_member_notice
    for member_notice in notices_resp.json()["data"] or []:
        post("deletemembernotice", cookies, {
            "member_notice_id": member_notice["id"],
            "csrf": csrf_token
        })

## Tasks
def add_or_configure_single(cookies, csrf_token):
    while True:
        name = input('Subgroup short name (e.g. "knowledge"): ').strip().lower()
        title = input('Subgroup title (e.g. "Institutional Knowledge Committee"): ')
        desc = input("Subgroup description (leave blank to re-use title): ")
        if len(desc) == 0:
            desc = title
        should_configure = True

        try:
            add_subgroup(name, desc, cookies, csrf_token)
        except GroupsIoRequestError as e:
            if e.type == "bad_request" and e.extra == "name already taken":
                should_configure = yes_no_input("Group already exists. Do you want to re-configure it?")
            else:
                raise e

        if should_configure:
            configure_subgroup(name, title, desc, cookies, csrf_token)
        print("Done! Add members at https://{}.groups.io/g/{}/subgroupdirectadd".format(TOP_LEVEL_GROUP_NAME, name))

        if yes_no_input("Do you want to create another one?") is False:
            break

def configure_all(cookies, csrf_token):
    # Docs: https://groups.io/api#get_sub_groups
    subgroups_resp = post("getsubgroups", cookies, {
        "group_name": TOP_LEVEL_GROUP_NAME,
        "limit": 100  # I sure hope we never have more than this...
    })
    for sg in subgroups_resp.json()["data"]:
        # Name is returned in parent-scoped form, e.g. swansway+technology
        unscoped_name = sg["name"].split("+")[1]
        configure_subgroup(unscoped_name, sg["title"], sg["desc"], cookies, csrf_token)

## Do the thing!

if __name__ == "__main__":

    # Docs: https://groups.io/api#login
    login_resp = post("login", cookies = None, data = {
        "email": os.environ.get(EMAIL_ENV_VAR) or input("User email: "),
        "password": os.environ.get(PASSWORD_ENV_VAR) or input("Password: "),
        "2fa": input("2fa code (leave blank if none): ")
    })
    cookies = login_resp.cookies
    csrf_token = login_resp.json()["user"]["csrf_token"]

    task = get_input("Do you want to add/configure a (s)ingle subgroup, or (a)ll subgroups?")
    if task == "s":
        add_or_configure_single(cookies, csrf_token)
    elif task == "a":
        configure_all(cookies, csrf_token)
    else:
        print("Invalid input, try again")
