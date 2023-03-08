import os
import time
import json
import email
import base64
import imaplib
import logging
import requests

from email.utils import parsedate_tz, mktime_tz
from logging.handlers import RotatingFileHandler


def process_email(now, email_raw, delay, signal_spam_account):
    """Process the email considered like spam

    :param now: timestamp from now
    :param email_raw: email content to be processed
    :param delay: (optional) ignored all spams below this delay
    :param signal_spam_account: Signal Spam account credentials
    :return: {@link #send_report}
    """
    email_message = email.message_from_bytes(email_raw)
    sender = email_message["from"]
    date = email_message["date"]

    if delay is not None:
        tt = parsedate_tz(date)
        timestamp = mktime_tz(tt)

        if (now - timestamp) < delay:
            return False # Ignore this email for the moment

    return send_report(signal_spam_account, sender, date, email_raw)


def signal_spam(mailbox):
    """Connects to the email account and process spam

    :param mailbox: Mailbox configuration
    :return: void
    """
    server = mailbox["server"]
    host = server["imap"]
    port = server["port"]

    signal_spam_account = mailbox["signal_spam_account"]

    delay = mailbox["delay"]
    now = int(time.time())

    if server["ssl"]:
        box = imaplib.IMAP4_SSL(host, port)
    else:
        box = imaplib.IMAP4(host, port)

    box.login(mailbox["username"], mailbox["password"])
    try:
        exist, nb_mails = box.select(mailbox["junk"])
        nb_mails = nb_mails[0]

        if exist == "OK":
            if int(nb_mails) > 0:
                typ, data = box.search(None, 'ALL')

                for num in data[0].split():
                    typ, data = box.fetch(num, '(RFC822)')

                    if process_email(now, data[0][1], delay, signal_spam_account):
                        box.store(num, '+FLAGS', '\\Deleted')
                box.expunge()
            box.close()
        else:
            logging.critical(nb_mails)

    except imaplib.IMAP4.error as e:
        logging.critical(e)
    finally:
        box.logout()


def send_report(account, sender, date, mail_content):
    """Send a report to Signal Spam

    :param account:
    :param sender: e-mail of the sender
    :param date: date of mail
    :param mail_content: content of the email to report
    :return: true if the report was sent, else false
    """
    url = config["config"]["signal_spam_url"]
    timeout = config["config"]["user_agent"]["timeout"]
    headers = {
        'User-Agent': config["config"]["user_agent"]["agent"],
    }

    logging.info("Spam report: " + sender + " sent on " + date)

    try:
        response = requests.post(url=url,
                                 timeout=timeout,
                                 headers=headers,
                                 auth=(account["username"], account["password"]),
                                 data={"message": base64.b64encode(mail_content)}
                                 )

        if response.status_code == 200 or response.status_code == 202:
            return True

        logging.critical("Sending the spam report failed [code: " + str(response.status_code) + "]")
    except requests.ConnectionError as e:
        logging.critical(e)
    except requests.Timeout as e:
        logging.critical(e)

    return False


def signal_spams():
    """Starts processing for each email account

    :return: void
    """
    servers = config["servers"]
    signal_spam_accounts = config["accounts"]["signal_spam"]
    mailbox_accounts = config["accounts"]["mailbox"]

    for key, value in mailbox_accounts.items():
        if value["enabled"]:
            logging.info("Check email account id="+ key)
            mailbox = value
            mailbox["server"] = servers[mailbox["server"]]
            mailbox["signal_spam_account"] = signal_spam_accounts[mailbox["signal_spam_account"]]

            try:
                signal_spam(mailbox)
            except imaplib.IMAP4.error as e:
                logging.critical(e)


# Main
if __name__ == '__main__':
    current_file = os.path.basename(__file__)

    # Logger Settings
    logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] %(message)s")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    fileHandler = RotatingFileHandler(current_file + ".log", maxBytes=1000000, backupCount=5)  # Max 6 mb of logs
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    pid = str(os.getpid())
    pidfile = "/tmp/" + os.path.splitext(current_file)[0] + ".pid"

    if os.path.isfile(pidfile):
        logging.critical("Another instance Signal Spam is running !")
        exit(0)

    f = open(pidfile, 'w')
    f.write(pid)
    f.close()

    try:
        config_file_url = "config.json"
        with open(config_file_url) as config_file:
            config = json.load(config_file)
            if config:
                logging.info("Configuration loaded, start Signal Spam")
                signal_spams()
            else:
                logging.critical("No configuration loaded")
    except IOError as e:
        logging.critical(e)
    finally:
        logging.info("Stop Signal Spam")
        os.unlink(pidfile)