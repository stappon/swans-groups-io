# groups.io subgroup creation script
This script creates Swans Market Cohousing groups.io subgroups and changes some default settings to values that work for us. It can also change those default settings for existing groups.

After running this script, you will need to add the group members to the group via the groups.io web interface.

## Setup
* Install Python 3
* Make a virtual environment:
```
python3 -m venv venv
source venv/bin/activate
```
* `pip3 install -r requirements.txt`(for requests library)
* Optional: Set the environment variables `GROUPSIO_EMAIL` and `GROUPSIO_PASSWORD` to avoid having to type your login info on every run
* `python3 create_subgroups.py`
* `deactivate` to exit virtual environment when done

