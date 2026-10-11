from learner import Learner

learner = Learner()

learner.update("action1", 4.0, {})
learner.update("action2", 2.0, {})

print("Total reward:", learner.total_reward)
print("Steps:", learner.steps)
print("Average reward:", learner.average_reward())