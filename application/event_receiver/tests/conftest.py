from testfixtures import LogCapture
from pytest import fixture


@fixture()
def log_capture():
    with LogCapture(names="lambda") as capture:
        yield capture


@fixture
def change_event():
    change_event = PHARMACY_STANDARD_EVENT.copy()
    yield change_event


# Please update when an official event is created
PHARMACY_STANDARD_EVENT = {
    "body": {
        "SearchKey": "ANEI1245",
        "ODSCode": "FX111",
        "OrganisationName": "My Test Pharmacy",
        "OrganisationTypeId": "PH1",
        "OrganisationType": "Pharmacy",
        "OrganisationStatus": "Visible",
        "ServiceType": "PHA",
        "ServiceSubType": "COMPH",
        "SummaryText": "",
        "URL": "https://my-pharmacy.com/",
        "Address1": "85 Peachfield Road",
        "Address2": None,
        "Address3": None,
        "City": "CHAPEL ROW",
        "County": "South Godshire",
        "Latitude": 53.38030624389648,
        "Longitude": -1.4826949834823608,
        "Postcode": "RG7 1DB",
        "Phone": "123456789",
        "Email": "health.my-pharmacy@nhs.net",
        "Website": "https://my-pharmacy.com/health-service",
        "OrganisationSubType": None,
        "OrganisationAliases": [],
    }
}
