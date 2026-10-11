from reward import calculate_reward

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

print("Reward:", reward)