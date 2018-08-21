import numpy as np
import logging

class Verwalter:
    
    def __init__(self):
        self.bilanz = np.empty((0,0))
        self.users = {}


    def get_key(self, user_id):
        if user_id not in self.users.keys():
            logging.error("Requested user_id not found: %i"%user_id)
            return -1

        return self.users[user_id]


    '''def add_user(self, user_id):
        if(user_id in self.users.keys()):
            logging.error("User %i is already in database and won't be added again"%(user_id))
            return False
        
        key = len(self.users)
        self.users[user_id] = key
        logging.info("User %i has been added to database with key %i"%(user_id, key))
        return True'''

    
    def ensure_user(self, user_id):
        if user_id not in self.users.keys():
            key = len(self.users)
            self.users[user_id] = key

            bilanz_neu = np.zeros( (key+1, key+1) )

            for i in range(key):
                for j in range(key):
                    bilanz_neu[i,j] = self.bilanz[i,j]

            self.bilanz = bilanz_neu

            logging.info("User %i has been added to database with key %i"%(user_id, key))



    def add_debt(self, von_id, an_id, betrag):

        if von_id == an_id:
            logging.debug("Adding debt to self attempted. How did this happen?")
            return


        # Ensuring for each id pair there is only one value
        if von_id > an_id:
            temp = an_id
            an_id = von_id
            von_id = temp
            betrag *= -1.

        self.ensure_user(von_id)
        self.ensure_user(an_id)

        self.bilanz[self.get_key(von_id), self.get_key(an_id)] += betrag
        logging.info("Debt from user %i to user %i has been increased by %.2f€"%(von_id, an_id, betrag))


    def get_balance(self, user_id):
        key = self.get_key(user_id)

        debts = []

        for i in self.users:
            if i == user_id:
                continue
            key_target = self.get_key(i)
            debt = self.bilanz[key, key_target]
            debt -= self.bilanz[key_target, key]
            if round(abs(debt), 2) >= 0.01:
                debts.append((i, debt))

        return debts
