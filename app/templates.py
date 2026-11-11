"""Fixed wording. The model never writes a whole email: code picks the template
and the model supplies at most one short acknowledgement sentence, which is
screened. Edit wording in vault/Templates, then mirror it here via pull request."""

FIRST_REPLY_DETAILED = """Hi {first_name},

Thanks so much for reaching out. My name is Danny, I'm the Executive Producer at Origin Films.

{ack}Thank you for sharing those details. I'll review everything with the team so we can come back to you with the right approach.

In the meantime, the best next step is a quick call so we can understand what you're looking for. You can book a time that suits you here:
{booking_link}

Talk soon,
Danny"""

FIRST_REPLY_VAGUE = """Hi {first_name},

Thanks so much for reaching out. My name is Danny, I'm the Executive Producer at Origin Films.

{ack}To give you an accurate quote and approach, it would help to know a little more about the project. If you have any reference videos you like, or more information on what you have in mind, please send them over.

The easiest way to go through it is a quick call. You can book a time that suits you here:
{booking_link}

Talk soon,
Danny"""

FOLLOW_UPS = {
    1: """Hi {first_name},

Just checking in. Do you have any questions or concerns I can help with?

If it's easier to talk it through, you can book a call here:
{booking_link}

Danny""",
    2: """Hi {first_name},

Following up on your project. Is there any more information you can share with us? Even rough notes or a reference video help us plan the right approach.

Danny""",
    3: """Hi {first_name},

I haven't heard back from you, so I wanted to ask directly: do you still want to move forward with this project?

Danny""",
    4: """Hi {first_name},

I'll assume the timing isn't right, so I'll close this out on our side for now. If things change, just reply to this email and we'll pick it right back up.

All the best,
Danny""",
}


def render_first_reply(first_name: str, detailed: bool, ack: str, booking_link: str) -> str:
    t = FIRST_REPLY_DETAILED if detailed else FIRST_REPLY_VAGUE
    ack = (ack.strip() + " ") if ack and ack.strip() else ""
    return t.format(first_name=first_name or "there", ack=ack, booking_link=booking_link)


def render_follow_up(step: int, first_name: str, booking_link: str) -> str:
    return FOLLOW_UPS[step].format(first_name=first_name or "there", booking_link=booking_link)
