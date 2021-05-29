import numpy as np


def brownian_motion(init_price, num_steps, delta_t, sigma=1, seed=None):
    if seed is not None:
        np.random.seed(seed)
    dW = np.sqrt(delta_t) * np.random.randn(num_steps) * sigma
    W = init_price + np.cumsum(dW)
    return W
