from os import environ, getenv
from logging import getLogger
from os import environ, getenv
from typing import Any, List

from boto3 import client
from nhs import NHSEntity
from psycopg2 import connect

logger = getLogger("lambda")
secrets_manager = client("secretsmanager", region_name=getenv("AWS_REGION", default="eu-west-2"))
VALID_SERVICE_TYPES = {13, 131, 132, 134, 137}
VALID_STATUS_ID = 1


class DoSService:
    """Class to represent a DoSService"""

    # These values are which columns are selected from the database and then
    # are passed in as attributes into the DoSService object.
    #
    # example: Put 'postcode' in this list and you can use service.postcode in
    # the object
    db_columns = [
        "id",
        "uid",
        "name",
        "odscode",
        "address",
        "town",
        "postcode",
        "web",
        "email",
        "fax",
        "nonpublicphone",
        "typeid",
        "parentid",
        "subregionid",
        "statusid",
        "createdtime",
        "modifiedtime",
        "publicphone",
        "publicname",
    ]

    def __init__(self, db_cursor_row):
        """Sets the attributes of this object to those found in the db row
        Args:
            db_cursor_row (dict): Change Request changes
        """
        for i, attribute_name in enumerate(self.db_columns):
            attrbute_value = db_cursor_row[i]
            setattr(self, attribute_name, attrbute_value)

    def __repr__(self):
        """Returns a string representation of this object"""
        if self.publicname is not None:
            name = self.publicname
        elif self.name is not None:
            name = self.name
        else:
            name = "NO-VALID-NAME"

        return f"<uid={self.uid} ods={self.odscode} type={self.typeid} status={self.statusid} name='{name}'>"

    def ods5(self) -> str:
        """Returns the ods5 code for this service

        Returns:
            str: First 5 digits of odscode
        """
        return self.odscode[0:5]

    def get_changes(self, nhs_entity: NHSEntity) -> dict:
        """Returns a dict of the changes that are required to get
        the service inline with the given nhs_entity
        """
        changes = {}
        add_field_to_change_request_if_not_equal(changes, "website", self.web, nhs_entity.Website)
        add_field_to_change_request_if_not_equal(changes, "postcode", self.postcode, nhs_entity.Postcode)
        add_field_to_change_request_if_not_equal(changes, "publicphone", self.publicphone, nhs_entity.Phone)
        add_field_to_change_request_if_not_equal(changes, "publicname", self.publicname, nhs_entity.OrganisationName)
        add_address_to_change_request_if_not_equal(changes, "address", self.address, nhs_entity)
        return changes


def add_field_to_change_request_if_not_equal(changes: dict, change_key: str, dos_value: str, nhs_uk_value: str) -> dict:
    """Adds field to the change request if the field is not equal
    Args:
        changes (dict): Change Request changes
        change_key (str): Key to add to the change request
        dos_value (str): Field from the DoS database for comparision
        nhs_uk_value (str): NHS UK Entity value for comparision

    Returns:
        dict: Change Request changes
    """
    logger.debug(f"Comparing {change_key} values")
    if compare_values(dos_value, nhs_uk_value):
        changes[change_key] = nhs_uk_value
    return changes


def add_address_to_change_request_if_not_equal(
    changes: dict, change_key: str, dos_address: str, nhs_uk_entity: NHSEntity
) -> dict:
    """Adds the address to the change request if the address is not equal

    Args:
        changes (dict): Change Request changes
        change_key (str): Key to add to the change request
        dos_address (str): Address from the DoS database for comparision
        nhs_uk_entity (NHSEntity): NHS UK Entity for comparision

    Returns:
        dict: Change Request changes
    """
    nhs_uk_address_lines = [
        nhs_uk_entity.Address1,
        nhs_uk_entity.Address2,
        nhs_uk_entity.Address3,
        nhs_uk_entity.City,
        nhs_uk_entity.County,
    ]
    nhs_uk_address = [address for address in nhs_uk_address_lines if address is not None and address != ""]
    nhs_uk_address_string = "$".join(nhs_uk_address)
    if compare_values(dos_address, nhs_uk_address_string):
        changes[change_key] = nhs_uk_address
    return changes


def compare_values(dos_value: str, nhs_uk_value: str) -> bool:
    """Compare if two values are equal. Values are converted to string and compared.

    Args:
        dos_value (str): First value to compare
        nhs_uk_value (str): Second value to compare

    Returns:
        bool: False if equal, True if not equal
    """
    not_equal = False
    if dos_value != nhs_uk_value:
        logger.debug(f"{dos_value=} != {nhs_uk_value=}")
        not_equal = True
    return not_equal


def dummy_dos_service() -> DoSService:
    """Creates a DoSService Object with random data for the unit testing"""
    test_data = []
    for col in DoSService.db_columns:
        random_str = "".join(random.choices("ABCDEFGHIJKLM", k=8))
        test_data.append(random_str)
    return DoSService(test_data)


def get_matching_dos_services(odscode: str) -> List[DoSService]:
    """Retrieves DoS Services from DoS database

    input:  ODSCode

    output: List of DoSService objects with matching first 5 digits

            of ODSCode, taken from DoS database
    """

    logger.info(f"Searching for DoS services with ODSCode that matches first 5 digits of '{odscode}'")

    # Get DB details from env variables
    server = environ["DB_SERVER"]
    port = environ["DB_PORT"]
    db_name = environ["DB_NAME"]
    db_user = environ["DB_USER_NAME"]
    db_password = environ["DB_PASSWORD"]

    # Connect to Database
    logger.info(f"Attempting connection to database '{server}'")
    logger.debug(f"host={server}, port={port}, dbname={db_name}, user={db_user}, password={db_password}")
    db = connect(host=server, port=port, dbname=db_name, user=db_user, password=db_password, connect_timeout=30)

    # Create and run SQL Command with inputted odscode SELECTING columns
    # defined at top of file and using the 'LIKE' command to match first
    # 5 digits of ODSCode
    sql_command = f"SELECT {', '.join(DoSService.db_columns)} FROM services WHERE odscode LIKE '{odscode[0:5]}%'"
    logger.info(f"Created SQL command to run: {sql_command}")
    c = db.cursor()
    c.execute(sql_command)
    # Create list of DoSService objects from returned rows
    services = [DoSService(row) for row in c.fetchall()]
    c.close()
    return services
