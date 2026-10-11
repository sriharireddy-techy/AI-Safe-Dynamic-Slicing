from reward import calculate_reward
from learner import Learner


previous_state = {
    "urllc_latency": 20,
    "embb_throughput": 8,
    "packet_loss": 2
}

new_state = {
    "urllc_latency": 10,
    "embb_throughput": 9,
    "packet_loss": 1
}


reward = calculate_reward(previous_state, None, new_state)

learner = Learner()
learner.update("increase_bandwidth", reward, new_state)

print("Reward:", reward)
print("Total reward:", learner.total_reward)
print("Steps:", learner.steps)
print("Average reward:", learner.average_reward())