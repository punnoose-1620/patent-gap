import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from env_controller import (
    getEmailConfirmationUrl,
    getEmailSenderAddress,
    getGmailAppPassword,
    getGmailSmtpHost,
    getGmailSmtpPort,
    getGmailUseTls,
)


SENDER_EMAIL = getEmailSenderAddress()
GMAIL_APP_PASSWORD = getGmailAppPassword()
GMAIL_SMTP_HOST = getGmailSmtpHost()
GMAIL_SMTP_PORT = getGmailSmtpPort()
GMAIL_USE_TLS = getGmailUseTls()
DEFAULT_CONFIRMATION_URL = getEmailConfirmationUrl()

EMAIL_CONFIRMATION_TEMPLATE = """
<html>
  <body>
    <p>Hey, you've registered your account with Patent Gap using the email {email_id}.</p>
    <p>Please click the button below to confirm your email.</p>
    <p>
      <a href="{confirmation_url}" style="display:inline-block;padding:10px 16px;background:#1f7a5c;color:#ffffff;text-decoration:none;border-radius:4px;">
        Confirm Email
      </a>
    </p>
  </body>
</html>
"""

INFRINGEMENT_NOTIFICATION_TEMPLATE = """
<html>
  <body>
    <p>Your {patent_name} patent has encountered {infringement_count} possible infringements on Patent Gap.</p>
  </body>
</html>
"""


def ConfirmEmailBody(email_id, url):
    confirmation_url = url or DEFAULT_CONFIRMATION_URL
    return EMAIL_CONFIRMATION_TEMPLATE.format(
        email_id=email_id,
        confirmation_url=confirmation_url
    )


def InfringementAlertBody(patent_name, infringement_count):
    return INFRINGEMENT_NOTIFICATION_TEMPLATE.format(
        patent_name=patent_name,
        infringement_count=infringement_count
    )


def SendMail(body, recipient_email):
    if not body or not recipient_email:
        return False
    if not SENDER_EMAIL or not GMAIL_APP_PASSWORD:
        print('ERROR: Missing Gmail sender email or app password configuration')
        return False

    message = MIMEMultipart('alternative')
    message['From'] = SENDER_EMAIL
    message['To'] = recipient_email
    message['Subject'] = 'Patent Gap Notification'
    message.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=20) as server:
            server.ehlo()
            if GMAIL_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, [recipient_email], message.as_string())
        return True
    except Exception as e:
        print(f'ERROR: Failed to send email to {recipient_email}: {str(e)}')
        return False
