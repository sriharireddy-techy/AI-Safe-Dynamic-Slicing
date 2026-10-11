class Learner:

    def __init__(self):
        self.total_reward = 0.0
        self.steps = 0

    def update(self, action, reward, context):
        self.total_reward += reward
        self.steps += 1

    def average_reward(self):
        if self.steps == 0:
            return 0.0

        return self.total_reward / self.steps