from json import dumps
from logging import getLogger
from os import environ, getenv

from aws_lambda_powertools import Tracer
from boto3 import client
from change_request import ChangeRequest
from common.logger import setup_logger
from dos import VALID_SERVICE_TYPES, VALID_STATUS_ID, get_matching_dos_services
from nhs import NHSEntity

logger = getLogger("lambda")
tracer = Tracer()
lambda_client = client("lambda", region_name=getenv("AWS_REGION", default="eu-west-2"))
expected_env_vars = ("DB_SERVER", "DB_PORT", "DB_NAME", "DB_USER_NAME", "EVENT_SENDER_LAMBDA_NAME")


class EventProcessor:
    matching_services: list
    change_requests: list

    def __init__(self, nhs_entity):
        self.nhs_entity = nhs_entity

    def get_matching_services(self):
        """Using the nhs entity attributed to this object, it finds the matching DoS services from the db
        and filters the results"""

        # Check database for services with same first 5 digits of ODSCode
        matching_services = get_matching_dos_services(self.nhs_entity.ODSCode)
        logger.info(
            f"Found {len(matching_services)} services in DB with matching first 5 chars of ODSCode: {matching_services}"
        )

        # Filter for services with valid type and status
        matching_services = [
            s for s in matching_services if int(s.typeid) in VALID_SERVICE_TYPES and int(s.statusid) == VALID_STATUS_ID
        ]
        logger.info(
            f"Found {len(matching_services)} services with typeid in whitelist "
            f"{VALID_SERVICE_TYPES} and status id = {VALID_STATUS_ID}: {matching_services}"
        )

        # Assign result to attribute and return
        self.matching_services = matching_services
        return self.matching_services

    def get_change_requests(self) -> dict:
        """Generates change requests needed for the found services to make them inline with the NHS Entity

        Returns:
            dict: A dictionary of change requests
        """
        change_requests = []
        for service in self.matching_services:
            # Find changes, don't make a change req if none found
            changes = service.get_changes(self.nhs_entity)
            if len(changes) == 0:
                continue
            cr = ChangeRequest(service.id, changes).get_change_request()
            change_requests.append(cr)
        logger.info(f"Created {len(change_requests)} change requests {dumps(change_requests, indent=2, default=str)}")
        # Assign to attribute and return
        self.change_requests = change_requests
        return self.change_requests

    def send_changes(self):
        """Sends change request payload off to next part of workflow
        [Which at the moment is straight to the next lambda]
        """
        assert self.change_requests is not None
        for change_payload in self.change_requests:
            response = lambda_client.invoke(
                FunctionName=environ["EVENT_SENDER_LAMBDA_NAME"],
                InvocationType="Event",
                Payload=change_payload,
            )
            logger.info(f"Sent off change payload for id={change_payload['service_id']}\n{response}")


@tracer.capture_lambda_handler()
@setup_logger
def lambda_handler(event, context):
    """Entrypoint handler for the event_receiver lambda

    Args:
        event (Dict[str, Any]): Lambda function invocation event
        context (LambdaContext): Lambda function context object

    Event: The event payload should contain a NHS Entity (Service)

    Some code may need to be changed if the exact input format is changed.

    """

    # Check all required env vars are present
    for env_var in expected_env_vars:
        if env_var not in environ:
            err_msg = f"Environmental variable {env_var} not present"
            logger.error(err_msg)
            return {"statusCode": 400, "error": err_msg}

    # Create NHS Entity object (the pharmacy)
    nhs_entity = NHSEntity(event)
    logger.info(f"Begun event processor function for NHS Entity: {dumps(nhs_entity.__dict__, indent=2, default=str)}")

    # Create processor using our NHS Entity
    event_processor = EventProcessor(nhs_entity)
    matching_services = event_processor.get_matching_services()

    # IF NO MATCHING SERVICES FOUND - logger error and return/end
    if len(matching_services) == 0:
        err_msg = f"No matching DOS services found that fit all criteria for ODSCode '{nhs_entity.odscode}'"
        logger.error(err_msg)
        return {"statusCode": 400, "error": err_msg}
    # Generate the change requests (if any are needed)
    event_processor.get_change_requests()
    # Either send off the change requests or not depending on option
    if event.get("send_changes", False) is True:
        event_processor.send_changes()
    else:
        logger.info(f"'send_changes' argument in event payload is set to False. Change requests will not be sent")
