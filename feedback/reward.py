SLA_LIMIT = 15.0


def calculate_reward(previous_state, action, new_state):
    reward = 0.0

    # Lower URLLC latency is better
    if new_state["urllc_latency"] < previous_state["urllc_latency"]:
        reward += 2.0
    else:
        reward -= 2.0

    # Higher eMBB throughput is better
    if new_state["embb_throughput"] > previous_state["embb_throughput"]:
        reward += 1.0
    else:
        reward -= 1.0

    # Lower packet loss is better
    if new_state["packet_loss"] <= previous_state["packet_loss"]:
        reward += 1.0
    else:
        reward -= 1.0

    # Penalize URLLC SLA violation
    if new_state["urllc_latency"] > SLA_LIMIT:
        reward -= 5.0

    return reward