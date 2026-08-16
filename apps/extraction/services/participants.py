from django.conf import settings

def participants_from_email(email_message):
    addresses = set()

    if email_message.sender_email:
        addresses.add(email_message.sender_email.strip().lower())

    for recipient in email_message.recipients or []:
        addr = (recipient.get("email") or "").strip().lower()
        if addr:
            addresses.add(addr)

    own = (settings.IMAP_USER or "").strip().lower()
    addresses.discard(own)

    return sorted(a for a in addresses if "@" in a)