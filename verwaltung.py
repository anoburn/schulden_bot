import numpy as np
import logging



class User:

    def __init__(self, user_id, index, bot):
        self.user_id = user_id
        self.index = index
        chat = bot.get_chat(chat_id=user_id)
        self.name = chat.first_name
        self.contacts = []
        self.state = 0
        self.targets = []
        self.available = False


    def add_contact(self, contact_id):
        if contact_id not in self.contacts:
            self.contacts.append(contact_id)



class Verwalter:
    
    def __init__(self):
        self.bilanz = np.empty((0,0))
        self.users = {}


    def get_index(self, user_id):
        if user_id not in self.users.keys():
            logging.error("Requested user_id not found: {}".format(user_id))
            return -1

        return self.users[user_id].index


    def ensure_user(self, user_id, bot):
        if user_id not in self.users.keys():
            index = len(self.users)
            self.users[user_id] = User(user_id, index, bot)

            bilanz_neu = np.zeros( (index+1, index+1) )

            for i in range(index):
                for j in range(index):
                    bilanz_neu[i,j] = self.bilanz[i,j]

            self.bilanz = bilanz_neu

            logging.info("User %i has been added to database with index %i"%(user_id, index))


    def add_debt(self, von_id, an_id, betrag):

        if von_id == an_id:
            logging.debug("Adding debt to self attempted. How did this happen?")
            return

        # Ensuring for each id pair there is only one value
        if von_id > an_id:
            von_id, an_id = an_id, von_id
            betrag *= -1.

        assert von_id in self.users.keys()
        assert an_id  in self.users.keys()

        self.bilanz[self.get_index(von_id), self.get_index(an_id)] += betrag
        logging.info("Debt from user %i to user %i has been increased by %.2f€"%(von_id, an_id, betrag))


    def get_balance(self, user_id):
        index = self.get_index(user_id)

        debts = []

        for user in self.users.values():
            i = user.user_id
            if i == user_id:
                continue
            target_index = self.get_index(i)
            debt = self.bilanz[index, target_index]
            debt -= self.bilanz[target_index, index]
            if round(abs(debt), 2) >= 0.01:
                debts.append((user.name, debt))
        return debts
