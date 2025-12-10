import base64
import json
import os
import logging
import functions_framework
from cloudevents.http import CloudEvent

import sendgrid
from sendgrid.helpers.mail import Mail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email_sendgrid(to: str, subject: str, body: str, sender: str) -> dict:
    """Send an email using SendGrid API."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY environment variable not set")
    
    sg = sendgrid.SendGridAPIClient(api_key)
    mail = Mail(
        from_email=sender,
        to_emails=to,
        subject=subject,
        plain_text_content=body
    )
    response = sg.send(mail)
    return {
        "status_code": response.status_code,
        "body": response.body,
        "headers": dict(response.headers)
    }


@functions_framework.cloud_event
def gcf_send_email(cloud_event: CloudEvent):
    """
    Cloud Function triggered by Pub/Sub via Eventarc.
    Expects Pub/Sub message data to contain JSON with:
    {
      "email": "student@school.edu",
      "name": "Student Name",
      "subject": "Welcome!",
      "body": "Hello ...",
      "event_type": "CustomerCreated"
    }
    """
    try:
        # Get the Pub/Sub message data (base64-encoded)
        pubsub_message = cloud_event.data.get("message", {})
        data_b64 = pubsub_message.get("data", "")
        
        if not data_b64:
            logger.error("No data in Pub/Sub message")
            return
        
        # Decode and parse the message
        payload_raw = base64.b64decode(data_b64).decode("utf-8")
        logger.info("Decoded pubsub data: %s", payload_raw)
        payload = json.loads(payload_raw)
        
    except Exception as e:
        logger.exception("Failed to decode/parse pubsub message: %s", e)
        return
    
    # Extract email details
    to = payload.get("email")
    if not to:
        logger.error("No 'email' field in event payload; skipping")
        return
    
    event_type = payload.get("event_type", "Update")
    subject = payload.get("subject") or f"Notification: {event_type}"
    name = payload.get("name") or "User"
    body = payload.get("body") or (
        f"Hello {name},\n\n"
        f"This is an automated message from the Customer service.\n\n"
        f"Event: {event_type}\n\n"
        f"Regards"
    )
    
    # Send email
    try:
        sender = os.getenv("SENDGRID_SENDER_EMAIL", "noreply@example.com")
        res = send_email_sendgrid(to, subject, body, sender)
        logger.info("Email sent via SendGrid: status=%s", res["status_code"])
    except Exception as e:
        logger.exception("Failed to send email via SendGrid API: %s", e)