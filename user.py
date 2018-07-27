
class User:

    def __init__(self, user_id, bot):
        self.user_id = user_id
        chat = bot.get_chat(chat_id=user_id)
        self.name = chat.first_name
        self.contacts = []
        self.state = 0
        self.available = False

    def add_contact(self, contact_id):
        if contact_id not in self.contacts:
            self.contacts.append(contact_id)