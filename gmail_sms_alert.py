#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Retrieve messages from a Gmail account via POP3
and forward each of them as an SMS via the Orange API.
"""

import email
from email.header import decode_header
import logging
import poplib
import sys
import urllib
import xml.dom.minidom

# configure the logger
LOG_FILENAME = "/tmp/gmail_sms_alert.log"
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Gmail pop server
GMAIL_POP_URL = "pop.gmail.com"

# Orange API settings
#ORANGE_ACCOUNT = "ejavommo_7@yopmail.com"
ORANGE_SENDSMS_SERVICE_URL = "http://sms.beta.orange-api.net/sms/sendSMS.xml"
ORANGE_ACCESS_KEY = "1590beebf8a"
ORANGE_NUMBER_FR_ORANGE = "20345"
ORANGE_NUMBER_FR_OTHER_OP = "38100"
ORANGE_NUMBER_INTERNATIONAL = "+447797805210"

def send_sms(access_key, number, to, content):
    """
    Send an SMS, using the Orange API (http://api.orange.com).
    
    Input parameters:
      - access_key: The access key associated with your Orange API account
      - number:     A number depending on the country and operator of the recipient
      - to:         Recipient's phone number (for France : '336xxxxxxxx')
      - content:    The text message to send, in unicode encoding.
                    Truncated to 158 characters.

    Returns the tuple (server_status_code, server_status_message).
    See 'http://api.orange.com/fr/api/sms-api/documentation,3' for details.      
    """
    # Truncate the content to 158 characters, maximum size allowed for 1 SMS via Orange API
    # (should be 160, thanks Orange..)
    content = content[:158]
    # prepare the REST parameters
    REST_params = urllib.urlencode([('id', access_key),
                                    ('from', number),
                                    ('to', to),
                                    ('content', content.encode('latin1', 'replace'))])
    # forge the REST call url
    url = ORANGE_SENDSMS_SERVICE_URL + '?' + REST_params
    # do the call
    resp = urllib.urlopen(url)
    # handle the XML response
    xmldoc = xml.dom.minidom.parse(resp)
    status_code = int(xmldoc.getElementsByTagName('status_code')[0].firstChild.data)
    status_msg = xmldoc.getElementsByTagName('status_msg')[0].firstChild.data
    return (status_code, status_msg)

def __get_field(msg, field):
    """Return the value of a MIME header's field in unicode.
    
    If there are multiple fields with the same name, returns only the first one.
    """
    field, encoding = decode_header(msg.get(field))[0]
    if encoding:
        return field.decode(encoding, 'replace')
    else:
        return field.decode()

    
def __process_message(msg):
    """Notify the reception of the given msg via SMS.
    
    Function called for each new message retrieved.
    Expected input : an email.message.Message object.
    """
    # There can be multiple parts in a MIME message.
    # Try to get the first text/plain payload and convert it to unicode.
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            # "text/plain" payload found.
            # Could be in any encoding, try to properly convert it to unicode.
            charset = part.get_content_charset()
            payload = part.get_payload(decode=True)
            # get_payload can return None
            if payload:
                if charset:
                    payload = payload.decode(charset, 'replace')
                else:
                    payload = payload.decode()
            else:
                payload = u""
            # stop at the first text/plain payload found
            break
    else:
        # text/plain payload not found
        payload = u""

    # Send an alert via SMS.
    # The content will be '<from>|<subject>|<beginning of payload>'
    sms = __get_field(msg, 'From') + "|" + __get_field(msg, 'Subject') + "|" + payload
    # eliminate extra-spaces
    sms = " ".join(sms.split())
    # get the phone number to send the SMS to
    phone_number = int(sys.argv[3])
    # send the SMS
    status_code, status_msg = send_sms(ORANGE_ACCESS_KEY, ORANGE_NUMBER_FR_ORANGE, phone_number, sms)
    # log the result
    if status_code == 200:
        logging.debug("SMS sent successfuly to %s" % phone_number)
    else:
        logging.error("Error while sending the SMS. status_code = %d, status_message = '%s'" % (status_code, status_msg))
    

if __name__ == "__main__":
    import sys
    try:
        #check arguments
        if len(sys.argv) < 4:
            print "Usage: ./gmail_sms.py USERNAME PASSWORD PHONE_NUMBER"
            print "Example: ./gmail_sms.py firstname.lastname mypass 336xxxxxxxx"
            raise Exception("Not enough arguments")
        # connect to the gmail pop server with SSL support
        p = poplib.POP3_SSL(GMAIL_POP_URL)
        # try to authenticate
        p.user(sys.argv[1])
        p.pass_(sys.argv[2])
        try:
            # get new messages statistics
            (num_msgs, total_size) = p.stat()
            # process them
            for i in range(1, num_msgs + 1):
                # Retrieve message with ID 'i' as a list of lines
                return_code, msg, size = p.retr(i)
                # conversion to an email.message.Message object
                msg = email.message_from_string('\n'.join(msg))
                __process_message(msg)
            if not num_msgs:
                logging.debug("Nothing to process")
        finally:
            # properly close the connection
            p.quit()
    except:
        logging.error("Exception %s : %s" % (sys.exc_info()[0], sys.exc_info()[1]))
