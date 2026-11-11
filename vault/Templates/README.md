# Templates

Email wording the Inbound agent uses. The live copies are in `app/templates.py`; change both in the same pull request.
The agent never writes a whole email. Code picks a template and the model supplies at most one short acknowledgement sentence, which is screened and dropped if it mentions money, contracts, links or addresses.

- First reply, detailed inquiry
- First reply, vague inquiry
- Follow-ups 1 to 4, on business days 3, 6, 10 and 15 after the first reply
